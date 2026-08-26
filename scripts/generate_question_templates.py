"""Script sinh ngân hàng câu hỏi trắc nghiệm Toán 6 đa dạng (30-40 câu/bài, chuẩn Bloom 1-6) bằng LLM (DeepSeek/OpenAI).

Mỗi bài học (32 unit) được gọi DeepSeek qua 3 lượt chuyên đề (mỗi lượt 12 câu):
- Lượt 1: Lý thuyết, nhận biết, khái niệm (Bloom 1-2)
- Lượt 2: Tính toán, quy tắc, vận dụng (Bloom 2-4)
- Lượt 3: Bài toán thực tế, phân tích, đánh giá, sáng tạo (Bloom 4-6)
-> Tổng cộng: ~32-36 câu hỏi độc bản cho mỗi bài học (~1100 câu toàn bộ chương trình Toán 6).

Kết quả được lưu cố định vào: `data/question_templates_toan6.json`
để dùng cho việc seed bài tập LMS và phân tích lỗ hổng kiến thức.

Chạy:
    .venv\\Scripts\\python.exe scripts/generate_question_templates.py
    .venv\\Scripts\\python.exe scripts/generate_question_templates.py --force
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

import psycopg  # noqa: E402
from openai import OpenAI  # noqa: E402

OUTPUT_FILE = _ROOT / "data" / "question_templates_toan6.json"
SUBJECT_ID = 106
GRADE_NUMBER = 6

BATCH_PROMPTS = [
    {
        "name": "Lý thuyết & Khái niệm cơ bản (Bloom 1-2)",
        "instruction": """Tạo 12 câu trắc nghiệm tập trung vào ĐỊNH NGHĨA, KÝ HIỆU, KHÁI NIỆM, ĐẶC ĐIỂM, NHẬN DIỆN ĐÚNG/SAI:
- Bloom 1 (Nhớ - nhận biết ký hiệu, định nghĩa, phát biểu): 6 câu
- Bloom 2 (Hiểu - giải thích, so sánh, nhận diện ví dụ đúng): 6 câu
Yêu cầu câu hỏi ngắn gọn, rõ ràng, tập trung kiểm tra bản chất lý thuyết của bài.""",
    },
    {
        "name": "Tính toán & Vận dụng công thức (Bloom 2-4)",
        "instruction": """Tạo 12 câu trắc nghiệm tập trung vào BÀI TẬP TÍNH TOÁN, ÁP DỤNG CÔNG THỨC, TÌM X, BIẾN ĐỔI:
- Bloom 2 (Hiểu - tính toán cơ bản 1 bước): 3 câu
- Bloom 3 (Vận dụng - tính toán 2-3 bước, áp dụng quy tắc vào dạng bài quen thuộc): 6 câu
- Bloom 4 (Phân tích - tìm x có điều kiện, bài toán suy luận nhiều bước): 3 câu
Yêu cầu các số liệu tính toán cụ thể, logic, đáp án nhiễu phản ánh các lỗi tính toán phổ biến của học sinh.""",
    },
    {
        "name": "Ứng dụng thực tế & Đánh giá sáng tạo (Bloom 4-6)",
        "instruction": """Tạo 12 câu trắc nghiệm tập trung vào BÀI TOÁN THỰC TẾ ĐỜI SỐNG, SUY LUẬN TỔNG HỢP, ĐÁNH GIÁ:
- Bloom 4 (Phân tích - bài toán thực tế ghép nhiều yếu tố, phân tích bảng/hình ảnh): 4 câu
- Bloom 5 (Đánh giá - nhận xét phương án tối ưu, phát hiện lỗi sai trong lời giải): 4 câu
- Bloom 6 (Sáng tạo / Vận dụng cao - tình huống mở, thiết kế bài toán, giải quyết vấn đề thực tiễn): 4 câu
Yêu cầu bài toán thực tế gần gũi với học sinh lớp 6 (mua sắm, chia nhóm, nhiệt độ, sân trường, tiền tiết kiệm...).""",
    },
]


def get_llm_client() -> tuple[OpenAI, str]:
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        model = "deepseek-chat"
        print(f"[INFO] Sử dụng DeepSeek API: base={api_base}, model={model}", flush=True)
        return OpenAI(api_key=deepseek_key, base_url=api_base, timeout=90.0), model

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        model = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
        print(f"[INFO] Fallback OpenAI API: model={model}", flush=True)
        return OpenAI(api_key=openai_key, timeout=90.0), model

    raise ValueError("Không tìm thấy DEEPSEEK_API_KEY hoặc OPENAI_API_KEY trong .env")


def sanitize_json_string(text: str) -> str:
    """Làm sạch chuỗi JSON trước khi parse."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1)
    text = re.sub(r"//.*?\n", "\n", text)
    text = re.sub(r",\s*([\]}])", r"\1", text)
    return text


def generate_batch(
    client: OpenAI,
    model: str,
    unit_id: int,
    unit_name: str,
    chapter_name: str,
    batch_info: dict,
) -> list[dict]:
    """Gọi LLM sinh 1 batch 12 câu theo chuyên đề."""
    prompt = f"""Bạn là chuyên gia khảo thí môn Toán THCS (lớp 6) theo Chương trình GDPT 2018 (SGK Cánh Diều / Chân Trời Sáng Tạo).

Hãy soạn chính xác 12 câu hỏi trắc nghiệm (mỗi câu gồm 4 đáp án A, B, C, D) cho bài học:
- 📖 Chương: {chapter_name}
- 📖 Bài học: {unit_name}

YÊU CẦU CHUYÊN ĐỀ ĐỢT NÀY:
{batch_info['instruction']}

QUY TẮC BẮT BUỘC:
- Câu hỏi phải ĐẶC THÙ cho bài "{unit_name}".
- 4 đáp án (options) phải có dạng: ["A. ...", "B. ...", "C. ...", "D. ..."].
- "correct" là số nguyên (0, 1, 2 hoặc 3) chỉ đáp án đúng.
- "explanation": giải thích ngắn gọn 1-2 câu vì sao đáp án đó đúng.
- KHÔNG dùng "Tất cả các đáp án trên" hoặc "Không có đáp án nào".

Định dạng trả về duy nhất là JSON Object:
{{
  "questions": [
    {{
      "text": "Nội dung câu hỏi...",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct": 0,
      "bloom_level": 1,
      "explanation": "Giải thích ngắn gọn..."
    }}
  ]
}}
"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia khảo thí môn Toán THCS. Bạn CHỈ trả về dữ liệu định dạng JSON Object chuẩn có key 'questions'."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.35,
                max_tokens=6000,
            )
            content = response.choices[0].message.content or ""
            clean_content = sanitize_json_string(content)
            data = json.loads(clean_content, strict=False)
            questions = data.get("questions", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

            valid = []
            for q in questions:
                if isinstance(q, dict) and "text" in q and "options" in q:
                    opts = q.get("options", [])
                    if isinstance(opts, list) and len(opts) >= 4:
                        correct = int(q.get("correct", 0))
                        if correct < 0 or correct >= len(opts):
                            correct = 0
                        bloom = int(q.get("bloom_level", 2))
                        if bloom < 1 or bloom > 6:
                            bloom = 2
                        valid.append({
                            "text": str(q.get("text", "")).strip(),
                            "options": [str(o).strip() for o in opts[:4]],
                            "correct": correct,
                            "bloom_level": bloom,
                            "explanation": str(q.get("explanation", "")).strip(),
                        })

            if len(valid) >= 8:
                return valid
            print(f"      [WARN] Batch '{batch_info['name']}' chỉ parse được {len(valid)} câu, thử lại lần {attempt + 1}...", flush=True)
        except Exception as e:
            print(f"      [ERROR] Lỗi batch '{batch_info['name']}' (lần {attempt + 1}): {e}", flush=True)
            time.sleep(1.5)

    return []


def main():
    parser = argparse.ArgumentParser(description="Sinh ngân hàng câu hỏi trắc nghiệm Toán 6 đa dạng (30-40 câu/bài)")
    parser.add_argument("--force", action="store_true", help="Ghi đè lại toàn bộ các bài học")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL chưa được cấu hình.", flush=True)
        sys.exit(1)

    client, model = get_llm_client()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing_data: dict[str, dict] = {}
    if OUTPUT_FILE.exists() and not args.force:
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            print(f"[INFO] Đã đọc {len(existing_data)} unit từ file JSON hiện có: {OUTPUT_FILE}", flush=True)
        except Exception as e:
            print(f"[WARN] Không đọc được cache JSON cũ: {e}", flush=True)

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    u.id AS unit_id,
                    u.code,
                    u.name AS unit_name,
                    COALESCE(c.name, 'CHƯƠNG TỔNG HỢP') AS chapter_name,
                    u.parent_id
                FROM public.curriculum_units u
                LEFT JOIN public.curriculum_units c ON u.parent_id = c.id
                WHERE u.subject_id = %s AND u.grade_number = %s AND u.parent_id IS NOT NULL
                ORDER BY u.id
            """, (SUBJECT_ID, GRADE_NUMBER))
            units = cur.fetchall()

    print(f"\n=======================================================================", flush=True)
    print(f"🎯 BẮT ĐẦU SINH NGÂN HÀNG CÂU HỎI (30-40 CÂU/BÀI) CHO {len(units)} BÀI HỌC TOÁN 6", flush=True)
    print(f"=======================================================================\n", flush=True)

    for idx, (unit_id, code, unit_name, chapter_name, parent_id) in enumerate(units, 1):
        str_id = str(unit_id)
        current_unit_data = existing_data.get(str_id, {})
        current_questions = current_unit_data.get("questions", [])

        if not args.force and len(current_questions) >= 30:
            print(f"[{idx}/{len(units)}] Unit {unit_id} ({unit_name}) -> Đã đủ {len(current_questions)} câu, bỏ qua.", flush=True)
            continue

        print(f"[{idx}/{len(units)}] Đang sinh câu hỏi cho Unit {unit_id}: [{chapter_name}] -> {unit_name} (Hiện có: {len(current_questions)} câu)...", flush=True)
        
        # Deduplication set by normalized question text
        seen_texts = {re.sub(r"\s+", " ", q["text"].lower().strip()) for q in current_questions}
        unit_all_questions = list(current_questions)

        for b_idx, batch_info in enumerate(BATCH_PROMPTS, 1):
            # Nếu đã có nhiều câu và chỉ cần thêm một ít
            if len(unit_all_questions) >= 36:
                break

            print(f"   🔹 Lượt {b_idx}/3: {batch_info['name']}...", flush=True)
            batch_qs = generate_batch(client, model, unit_id, unit_name, chapter_name, batch_info)
            added_count = 0
            for q in batch_qs:
                norm_text = re.sub(r"\s+", " ", q["text"].lower().strip())
                if norm_text not in seen_texts:
                    seen_texts.add(norm_text)
                    unit_all_questions.append(q)
                    added_count += 1
            print(f"      -> Thu thập thêm {added_count} câu (Tổng hiện tại: {len(unit_all_questions)} câu).", flush=True)
            time.sleep(0.5)

        existing_data[str_id] = {
            "unit_id": unit_id,
            "unit_code": code,
            "unit_name": unit_name,
            "chapter_name": chapter_name,
            "parent_id": parent_id,
            "questions": unit_all_questions,
        }

        # Lưu ngay sau mỗi unit
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        print(f"   ✅ Hoàn thành Unit {unit_id}: Tổng cộng {len(unit_all_questions)} câu hỏi.\n", flush=True)

    total_all = sum(len(v.get("questions", [])) for v in existing_data.values())
    print(f"\n=======================================================================", flush=True)
    print(f"🎉 TỔNG KẾT: ĐÃ SINH & LƯU {total_all} CÂU HỎI TRẮC NGHIỆM ({len(existing_data)}/{len(units)} BÀI HỌC)", flush=True)
    print(f"📁 File đích: {OUTPUT_FILE}", flush=True)
    print(f"=======================================================================\n", flush=True)


if __name__ == "__main__":
    main()
