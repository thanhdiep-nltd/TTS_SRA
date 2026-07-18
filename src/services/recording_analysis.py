import json
import logging
import re
from uuid import UUID

import replicate
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.db.session import SessionLocal
from src.models.enums import RecordingRank
from src.models.tables import ClassroomRecording
from src.services.llm import get_llm

logger = logging.getLogger(__name__)


def format_time(seconds) -> str:
    if seconds is None:
        return "00:00"
    try:
        total_seconds = int(float(seconds))
        minutes = total_seconds // 60
        secs = total_seconds % 60
        return f"{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "00:00"


def transcribe_audio_whisperx(audio_url: str) -> list:
    """Gọi Replicate WhisperX API để chuyển đổi giọng nói thành text segments."""
    s = get_settings()
    if not s.replicate_api_token:
        raise ValueError("Cấu hình REPLICATE_API_TOKEN bị thiếu.")

    # Tự động trích xuất tên file và sinh Signed URL mới để đảm bảo liên kết luôn khả dụng cho Replicate tải về
    if audio_url:
        url_parts = audio_url.split("/")
        filename = url_parts[-1].split("?")[0]
        from pathlib import Path
        ext = Path(filename).suffix.lower()
        if ext in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}:
            bucket = url_parts[-2] if len(url_parts) >= 2 and url_parts[-2] in {"audios", "videos", "lectures"} else None
            from src.services.storage import generate_signed_audio_url
            try:
                audio_url = generate_signed_audio_url(filename, expires_in=3600, bucket=bucket)
                logger.info("Đã sinh Signed URL mới cho WhisperX: %s (bucket: %s)", audio_url, bucket)
            except Exception as e:
                logger.error(f"Không thể sinh Signed URL tự động cho WhisperX trong bucket {bucket}: {e}")

    client = replicate.Client(api_token=s.replicate_api_token, timeout=300.0)
    logger.info("Bắt đầu WhisperX transcription cho URL: %s", audio_url)

    output = client.run(
        "victor-upmeet/whisperx:655845d6190ef70573c669245f245892cd039df4b880a1e3a65852c09252f5cc",
        input={"audio_file": audio_url, "align_output": True, "diarization": False},
    )

    segments = []
    if isinstance(output, dict) and "segments" in output:
        raw_segments = output["segments"]
    elif hasattr(output, "segments"):
        raw_segments = output.segments
    elif isinstance(output, list):
        raw_segments = output
    else:
        logger.warning("Cấu trúc đầu ra WhisperX không mong đợi: %s", type(output))
        raw_segments = []

    for seg in raw_segments:
        start = seg.get("start") if isinstance(seg, dict) else getattr(seg, "start", None)
        text = seg.get("text") if isinstance(seg, dict) else getattr(seg, "text", "")
        speaker_label = seg.get("speaker") if isinstance(seg, dict) else getattr(seg, "speaker", None)

        if not speaker_label:
            speaker_label = "Người nói"
        else:
            speaker_label = speaker_label.replace("SPEAKER_", "Người nói ")

        segments.append({"time": format_time(start), "speaker": speaker_label, "text": text.strip()})

    return segments


def evaluate_pedagogy_llm(transcript_segments: list) -> dict:
    """Gọi LLM (OpenAI/DeepSeek qua get_llm()) để chấm điểm và đánh giá sư phạm."""
    transcript_text = ""
    for seg in transcript_segments:
        time_str = seg.get("time", "00:00")
        speaker = seg.get("speaker", "Người nói")
        text = seg.get("text", "")
        transcript_text += f"[{time_str}] {speaker}: {text}\n"

    prompt = f"""Dưới đây là văn bản được dịch ra từ một đoạn ghi âm (sẽ có vài từ sai chính tả do con người đọc và mô hình speech-to-text dịch nên bạn có thể chỉnh lại cho hợp ngữ cảnh).
Hãy đọc hiểu đoạn văn bản này và thực hiện các yêu cầu sau bằng tiếng Việt:
Bạn sẽ đóng vai là Ban Giám Hiệu (BGH) trường học, thực hiện hoạt động đổi mới: 'Sinh hoạt chuyên môn dựa trên nghiên cứu bài học' theo tinh thần Chương trình GDPT 2018 và Công văn 5512/BGDĐT. Thay vì chỉ soi xét lỗi của giáo viên, hãy tập trung phân tích sâu vào hoạt động học và mức độ chủ động của học sinh.

Nhiệm vụ của bạn là đưa ra báo cáo đánh giá chi tiết theo cấu trúc gồm 3 phần sau:

Phần 1. PHÂN TÍCH TIẾN TRÌNH VÀ HOẠT ĐỘNG CỦA GIÁO VIÊN
- Chuỗi hoạt động: Giáo viên có tổ chức đủ và hợp lý các bước: Khởi động -> Hình thành kiến thức -> Luyện tập -> Vận dụng hay không? Chỉ ra các mốc hội thoại tương ứng trong text thể hiện điều này.
- Cách tổ chức và giao nhiệm vụ: Giáo viên giao việc có rõ ràng, sinh động không? Có dùng phiếu học tập, sơ đồ tư duy hay yêu cầu thảo luận nhóm cụ thể không?
- Theo dõi, hỗ trợ và đúc kết: Giáo viên có chủ động tương tác, phát hiện học sinh gặp khó khăn để hướng dẫn không? Cách giáo viên chốt kiến thức nền tảng sau khi học sinh làm việc có chuẩn xác không?

Phần 2. PHÂN TÍCH HOẠT ĐỘNG CỦA HỌC SINH (Trọng tâm lớn nhất)
- Mức độ tiếp nhận nhiệm vụ: Dựa vào lời thoại của học sinh, các em có hiểu rõ yêu cầu của giáo viên không? Có hiện tượng mơ hồ không biết phải làm gì không?
- Tính chủ động và tương tác: Học sinh chủ động thảo luận, phát biểu phản biện hay chỉ trả lời thụ động khi bị gọi tên? Tỷ lệ lời thoại hoặc sự tham gia của học sinh chiếm khoảng bao nhiêu dựa trên văn bản?
- Hiệu quả sản phẩm học tập: Các câu trả lời, phần trình bày hoặc báo cáo nhóm của học sinh phản ánh mức độ đạt mục tiêu bài học thế nào? Ví dụ như đã nhận biết đúng đặc điểm thể loại, hoặc rút ra được bài học cốt lõi chưa?

Phần 3. ĐÁNH GIÁ CHUNG CỦA BGH VÀ GỢI Ý ĐỔI MỚI
- Ưu điểm nổi bật: Điểm sáng đáng khen nhất của tiết học xét theo tinh thần phát triển năng lực học sinh.
- Hạn chế hoặc điểm nghẽn: Những đoạn hội thoại nào cho thấy học sinh bị ngợp, mất tập trung, hoặc giáo viên bị sa đà vào giảng giải một chiều hay đọc chép cần chỉnh sửa.
- Giải pháp cải tiến cụ thể: Đề xuất cách thay đổi câu hỏi, thay đổi cách giao việc ở các điểm nghẽn đó để tiết học hiệu quả hơn.

Nội dung văn bản dịch:
\"\"\"
{transcript_text}
\"\"\"

Yêu cầu bắt buộc đầu ra phải là một đối tượng JSON hợp lệ (không kèm theo bất kỳ văn bản giải thích hay dẫn nhập nào khác ngoài JSON). Hãy sử dụng đúng cấu trúc sau:
{{
  "score": <điểm số đánh giá tổng quan từ 0.0 đến 10.0, định dạng số thực, ví dụ: 8.5>,
  "engagement": "<ước lượng tỷ lệ tương tác của học sinh, ví dụ: '85%'>",
  "rank": "<xếp loại: chỉ được chọn một trong ba mức key: 'EXCELLENT', 'SATISFACTORY', 'NEEDS_IMPROVEMENT'>",
  "ai_report": "<nội dung báo cáo chi tiết gồm Phần 1, Phần 2, Phần 3 theo đúng yêu cầu phân tích ở trên, được trình bày bằng định dạng markdown>"
}}"""

    logger.info("Đang gọi LLM qua get_llm() để đánh giá sư phạm...")
    llm = get_llm()
    messages = [
        SystemMessage(content="You are a professional pedagogical evaluator that outputs only clean JSON."),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)

    try:
        content_clean = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        data = json.loads(content_clean)
        # Validate key fields
        required = ["score", "engagement", "rank", "ai_report"]
        for k in required:
            if k not in data:
                raise KeyError(f"Thiếu key bắt buộc: {k}")
        return data
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Không thể parse kết quả JSON trực tiếp. Đang cố gắng trích xuất bằng regex... Lỗi: %s", e)
        json_match = re.search(r"(\{.*\})", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return data
            except json.JSONDecodeError:
                pass

        logger.error("Gọi LLM đánh giá thất bại hoặc không đúng định dạng. Sử dụng fallback.")
        return {
            "score": 5.0,
            "engagement": "N/A",
            "rank": "SATISFACTORY",
            "ai_report": f"### Lỗi Định Dạng Báo Cáo\nKhông thể phân tích phản hồi có cấu trúc tự động từ AI.\n\n**Phản hồi gốc:**\n{content}",
        }


def analyze_recording_background(recording_id: UUID) -> None:
    """Tiến trình chạy nền xử lý ghi âm qua WhisperX và LLM."""
    db = SessionLocal()
    try:
        recording = db.get(ClassroomRecording, recording_id)
        if not recording:
            logger.error("Không tìm thấy ClassroomRecording với ID: %s", recording_id)
            return

        # Cập nhật trạng thái bắt đầu
        recording.status = "processing"
        recording.progress = 10
        db.commit()

        # Step 1: Transcription WhisperX
        try:
            transcript_segments = transcribe_audio_whisperx(recording.audio_file_url)
            recording.transcript = transcript_segments
            recording.progress = 50
            db.commit()
        except Exception as e:
            logger.exception("Lỗi trong quá trình transcribe ghi âm: %s", recording_id)
            recording.status = "failed"
            recording.ai_report = f"### ❌ Lỗi Chuyển Đổi Giọng Nói (WhisperX)\n\nĐã xảy ra lỗi:\n```\n{str(e)}\n```"
            db.commit()
            return

        # Step 2: Đánh giá LLM
        try:
            eval_result = evaluate_pedagogy_llm(transcript_segments)
            recording.score = eval_result.get("score")
            recording.engagement = eval_result.get("engagement")

            # Map rank string to enum
            rank_str = eval_result.get("rank", "SATISFACTORY").upper()
            if rank_str == "EXCELLENT":
                recording.rank = RecordingRank.EXCELLENT
            elif rank_str == "NEEDS_IMPROVEMENT":
                recording.rank = RecordingRank.NEEDS_IMPROVEMENT
            else:
                recording.rank = RecordingRank.SATISFACTORY

            recording.ai_report = eval_result.get("ai_report")
            recording.status = "done"
            recording.progress = 100
            db.commit()
        except Exception as e:
            logger.exception("Lỗi trong quá trình chấm điểm LLM ghi âm: %s", recording_id)
            recording.status = "failed"
            recording.ai_report = f"### ❌ Lỗi Phân Tích Sư Phạm (LLM)\n\nĐã xảy ra lỗi:\n```\n{str(e)}\n```"
            db.commit()

    except Exception:
        logger.exception("Lỗi chạy nền không mong đợi với ghi âm: %s", recording_id)
    finally:
        db.close()
