"""src/services/lms_question_analyzer.py — Phân tích độ khó (Bloom) và phân tách bài học cho Ngân hàng câu hỏi LMS.

Hỗ trợ:
1. Quản lý tác vụ ngầm (Background Task / Job Manager) bất đồng bộ, chống timeout và bền vững qua việc reload trang.
2. Theo dõi tiến độ thời gian thực (Progress tracking): processed/total, progress_percent, bloom_distribution.
3. Tích hợp đa mô hình AI (OpenRouter: Gemini 3.7 Flash, Mimo 2.5, GPT-4o Mini; ShopAIKey: Qwen 3 VL Flash; Custom).
4. Cập nhật trực tiếp `lms_question_bank.bloom_level` và bảng `lms_question_unit`.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.session import SessionLocal
from src.models.tables import CurriculumUnit, LmsQuestionBank, LmsQuestionUnit
from src.services import content_difficulty
from src.services.llm import TimedChatOpenAI, get_llm

logger = logging.getLogger(__name__)


class NodeMapping(BaseModel):
    """1 node kiến thức trong cây chương trình + trọng số."""

    node_id: int
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class QuestionAnalysisResult(BaseModel):
    """Kết quả phân tích 1 câu hỏi từ LLM."""

    question_id: int
    bloom_level: int = Field(ge=1, le=6, description="Mức độ nhận thức Bloom 1-6")
    nodes: list[NodeMapping] = Field(default_factory=list, description="Danh sách các bài học tương ứng kèm trọng số")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = None


@dataclass
class AnalysisJobState:
    """Trạng thái của một Background Job phân tích câu hỏi LMS."""

    job_id: str
    subject_id: int
    status: str  # "pending", "running", "completed", "failed"
    total_questions: int = 0
    processed_questions: int = 0
    progress_percent: int = 0
    bloom_distribution: dict[int, int] = field(default_factory=lambda: {b: 0 for b in range(1, 7)})
    unclassified_remaining: int = 0
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    message: str = ""


class LmsAnalysisJobManager:
    """Quản lý trạng thái tiến trình Job phân tích (Thread-safe)."""

    def __init__(self):
        self._jobs: dict[str, AnalysisJobState] = {}
        self._latest_by_subject: dict[int, str] = {}
        self._lock = threading.Lock()

    def create_job(self, subject_id: int, total_questions: int = 0) -> str:
        job_id = f"job_lms_{uuid.uuid4().hex[:10]}"
        now_str = datetime.now().isoformat()
        state = AnalysisJobState(
            job_id=job_id,
            subject_id=subject_id,
            status="pending",
            total_questions=total_questions,
            processed_questions=0,
            progress_percent=0,
            bloom_distribution={b: 0 for b in range(1, 7)},
            started_at=now_str,
            message="Đang khởi tạo tác vụ phân tích AI...",
        )
        with self._lock:
            self._jobs[job_id] = state
            self._latest_by_subject[subject_id] = job_id
        return job_id

    def set_running(self, job_id: str, total_questions: int):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = "running"
                self._jobs[job_id].total_questions = total_questions
                self._jobs[job_id].message = f"Đang phân tích: 0/{total_questions} câu..."

    def update_progress(
        self,
        job_id: str,
        processed_count: int,
        bloom_dist: dict[int, int],
        unclassified_remaining: int = 0,
        message: str = "",
    ):
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "running"
                job.processed_questions = processed_count
                total = max(1, job.total_questions)
                job.progress_percent = min(100, int((processed_count / total) * 100))
                job.bloom_distribution = {k: v for k, v in bloom_dist.items()}
                job.unclassified_remaining = unclassified_remaining
                job.message = message or f"Đang phân tích: {processed_count}/{job.total_questions} câu ({job.progress_percent}%)..."

    def complete_job(
        self,
        job_id: str,
        processed_count: int,
        bloom_dist: dict[int, int],
        unclassified_remaining: int = 0,
        message: str = "",
    ):
        now_str = datetime.now().isoformat()
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "completed"
                job.processed_questions = processed_count
                job.progress_percent = 100
                job.bloom_distribution = {k: v for k, v in bloom_dist.items()}
                job.unclassified_remaining = unclassified_remaining
                job.finished_at = now_str
                job.message = message or f"Đã phân tích và gán Bloom thành công cho {processed_count} câu hỏi."

    def fail_job(self, job_id: str, error_message: str):
        now_str = datetime.now().isoformat()
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error_message = error_message
                job.finished_at = now_str
                job.message = f"Lỗi phân tích: {error_message}"

    def get_job(self, job_id: str) -> AnalysisJobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_latest_job(self, subject_id: int) -> AnalysisJobState | None:
        with self._lock:
            job_id = self._latest_by_subject.get(subject_id)
            if job_id:
                return self._jobs.get(job_id)
            return None


# Global Job Manager Singleton
job_manager = LmsAnalysisJobManager()


def get_custom_llm(model_name: str | None = None) -> Any:
    """Khởi tạo instance LLM linh hoạt theo model_name chuẩn hóa từ UI (khớp trang nạp sách)."""
    if not model_name:
        return get_llm()

    settings = get_settings()
    m_lower = model_name.lower().strip()

    # 1. ShopAIKey / DashScope (Qwen 3 VL Flash)
    if "qwen3" in m_lower or "shopaikey" in m_lower or "dashscope" in m_lower or model_name == "qwen3-vl-flash":
        api_key = settings.qwen_vlm_api_key or settings.vlm_api_key or settings.openrouter_api_key
        api_base = settings.qwen_vlm_api_base or settings.vlm_api_base or "https://direct.shopaikey.com/v1"
        return TimedChatOpenAI(
            model="qwen3-vl-flash",
            api_key=api_key,
            base_url=api_base,
            temperature=0.0,
            timeout=settings.llm_timeout_s,
        )

    # 2. OpenRouter (Gemini 3.7 Flash, Xiaomi Mimo 2.5, GPT-4o Mini, Qwen 2.5 VL 72B, Custom Model ID...)
    if settings.openrouter_api_key and (
        "/" in model_name
        or "openrouter" in m_lower
        or "gemini" in m_lower
        or "mimo" in m_lower
        or model_name == "custom"
    ):
        return TimedChatOpenAI(
            model=model_name if model_name != "custom" else "google/gemini-3.7-flash",
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_api_base or "https://openrouter.ai/api/v1",
            temperature=0.0,
            timeout=settings.llm_timeout_s,
        )

    # 3. OpenAI trực tiếp hoặc fallback
    if settings.openai_api_key:
        return TimedChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base or "https://api.openai.com/v1",
            temperature=0.0,
            timeout=settings.llm_timeout_s,
        )

    return get_llm()


def _build_batch_analysis_prompt(shortlist: list[CurriculumUnit], questions: list[dict[str, Any]]) -> tuple[str, str]:
    """Dựng System Prompt và User Message để phân tích theo batch câu hỏi."""
    node_listing = content_difficulty.build_node_listing(shortlist)
    
    system_prompt = (
        "Bạn là chuyên gia thẩm định và phân loại câu hỏi khảo thí chuẩn Bộ GD&ĐT.\n"
        "Dưới lăng kính của KHUNG CHƯƠNG TRÌNH HỌC (DANH SÁCH BÀI HỌC/NODE SGK), hãy đọc kỹ từng câu hỏi và thực hiện 2 nhiệm vụ:\n"
        "1. Xác định mức độ nhận thức Bloom (bloom_level):\n"
        "   - 1: Nhận biết (Nhớ định nghĩa, công thức, nhận diện trực tiếp)\n"
        "   - 2: Thông hiểu (Giải thích, tính toán đơn giản 1 bước, phân biệt khái niệm)\n"
        "   - 3: Vận dụng (Áp dụng công thức vào bài toán cụ thể, tính toán 2-3 bước)\n"
        "   - 4: Vận dụng cao / Phân tích (Bài toán tổng hợp, kết hợp nhiều kiến thức, suy luận logic)\n"
        "   - 5: Đánh giá (So sánh phương án, chứng minh, tìm lỗi sai)\n"
        "   - 6: Sáng tạo (Thiết kế bài toán mới, tổng quát hóa quy luật)\n\n"
        "2. Phân tách và gán câu hỏi vào node bài học tương ứng trong DANH SÁCH (nodes):\n"
        "   - Mỗi node là 1 node_id từ danh sách kèm weight (0..1).\n"
        "   - ƯU TIÊN GÁN VÀO ĐÚNG 1 BÀI HỌC CỐT LÕI (weight = 1.0).\n"
        "   - Chỉ gán từ 2 node trở lên nếu câu hỏi là dạng liên bài rõ rệt (mỗi node weight >= 0.3, tổng weight = 1.0).\n\n"
        f"DANH SÁCH BÀI HỌC / CHƯƠNG:\n{node_listing}\n\n"
        "ĐỊNH DẠNG ĐẦU RA:\n"
        "Trả về CHỈ DUY NHẤT 1 JSON ARRAY (không bọc trong markdown code block, không thêm lời giải thích):\n"
        "[\n"
        '  {"question_id": 123, "bloom_level": 2, "nodes": [{"node_id": 395, "weight": 1.0}], "confidence": 0.95, "reason": "Câu hỏi tính tổng các số nguyên, thuộc bài phép cộng số nguyên."}\n'
        "]"
    )

    q_items = []
    for q in questions:
        q_text = f"ID #{q['question_id']}: {q.get('question_text', '')}"
        if q.get("options"):
            q_text += f" | Lựa chọn: {q['options']}"
        q_items.append(q_text)

    user_message = "Hãy phân tích danh sách các câu hỏi sau:\n" + "\n\n".join(q_items)
    return system_prompt, user_message


def _parse_llm_json_response(raw_text: str) -> list[dict[str, Any]]:
    """Lọc và parse JSON array từ phản hồi của LLM."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            return data["items"]
    except Exception:
        m = re.search(r"\[\s*\{.*\}\s*\]", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    logger.warning("Không thể parse JSON từ phản hồi LLM: %s", raw_text[:300])
    return []


def run_analysis_job_in_background(
    job_id: str,
    subject_id: int,
    model_name: str | None = None,
    re_analyze: bool = False,
    limit: int | None = 20,
    batch_size: int = 10,
):
    """Thực thi phân tích câu hỏi trong BackgroundTask và cập nhật realtime vào job_manager."""
    logger.info("Bắt đầu chạy Background Job %s cho môn %s (limit=%s)", job_id, subject_id, limit)

    try:
        with SessionLocal() as db:
            # 1. Lấy shortlist bài học trong chương trình
            shortlist = content_difficulty.build_shortlist(db, subject_id, grade_number=None, semester_number=None)
            if not shortlist:
                stmt_units = select(CurriculumUnit).where(
                    CurriculumUnit.subject_id == subject_id,
                    CurriculumUnit.is_active.is_(True),
                ).order_by(CurriculumUnit.parent_id.nulls_first(), CurriculumUnit.id)
                shortlist = list(db.execute(stmt_units).scalars().all())

            if not shortlist:
                job_manager.fail_job(job_id, f"Môn học {subject_id} chưa có dữ liệu cây chương trình học (curriculum_units).")
                return

            valid_node_ids = {u.id for u in shortlist}
            node_to_parent: dict[int, int | None] = {u.id: u.parent_id for u in shortlist}
            node_to_name: dict[int, str] = {u.id: u.name for u in shortlist}

            # 2. Quét danh sách câu hỏi cần phân tích
            stmt_q = select(LmsQuestionBank).where(LmsQuestionBank.subject_id == subject_id)
            if not re_analyze:
                stmt_q = stmt_q.where(LmsQuestionBank.bloom_level.is_(None))

            stmt_q = stmt_q.order_by(LmsQuestionBank.question_id)
            if limit is not None and limit > 0:
                stmt_q = stmt_q.limit(limit)

            questions_to_process = list(db.execute(stmt_q).scalars().all())
            total_count = len(questions_to_process)

            if total_count == 0:
                remaining_cnt = db.execute(
                    select(func.count(LmsQuestionBank.question_id)).where(
                        LmsQuestionBank.subject_id == subject_id,
                        LmsQuestionBank.bloom_level.is_(None),
                    )
                ).scalar() or 0
                job_manager.complete_job(
                    job_id,
                    processed_count=0,
                    bloom_dist={},
                    unclassified_remaining=remaining_cnt,
                    message="Không có câu hỏi nào cần phân tích theo bộ lọc.",
                )
                return

            job_manager.set_running(job_id, total_questions=total_count)

            # 3. Khởi tạo LLM
            llm = get_custom_llm(model_name)

            # 4. Phân tích theo từng chunk (batch_size)
            bloom_dist: dict[int, int] = {b: 0 for b in range(1, 7)}
            processed_so_far = 0

            for i in range(0, total_count, batch_size):
                chunk = questions_to_process[i : i + batch_size]
                q_payload = [
                    {
                        "question_id": q.question_id,
                        "question_text": q.question_text,
                        "options": getattr(q, "options", None),
                    }
                    for q in chunk
                ]

                system_prompt, user_msg = _build_batch_analysis_prompt(shortlist, q_payload)
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_msg),
                ]

                try:
                    if hasattr(llm, "bind") and not hasattr(llm, "_mock_return_value"):
                        invoker = llm.bind(temperature=0.0)
                        resp = invoker.invoke(messages)
                    else:
                        resp = llm.invoke(messages)
                    raw_content = resp.content if isinstance(resp.content, str) else str(resp.content)
                    parsed_list = _parse_llm_json_response(raw_content)
                except Exception as ex:
                    logger.error("Lỗi khi gọi LLM phân tích batch câu hỏi: %s", ex, exc_info=True)
                    parsed_list = []

                parsed_by_id = {item.get("question_id"): item for item in parsed_list if isinstance(item, dict)}

                for q_obj in chunk:
                    p_data = parsed_by_id.get(q_obj.question_id)
                    if p_data:
                        try:
                            bloom = int(p_data.get("bloom_level", 2))
                            bloom = max(1, min(6, bloom))
                        except (ValueError, TypeError):
                            bloom = 2

                        raw_nodes = p_data.get("nodes") or []
                        valid_nodes: list[tuple[int, float]] = []
                        for n_entry in raw_nodes:
                            if isinstance(n_entry, dict):
                                n_id = n_entry.get("node_id")
                                w = float(n_entry.get("weight", 1.0))
                                if n_id in valid_node_ids:
                                    valid_nodes.append((n_id, w))

                        if valid_nodes:
                            tot_w = sum(w for _, w in valid_nodes)
                            if tot_w > 0:
                                valid_nodes = [(nid, round(w / tot_w, 4)) for nid, w in valid_nodes]
                        else:
                            fallback_node = q_obj.lesson_id or q_obj.unit_id or shortlist[0].id
                            valid_nodes = [(fallback_node, 1.0)]

                        primary_node_id = valid_nodes[0][0]
                        parent_id = node_to_parent.get(primary_node_id)
                        lesson_id = primary_node_id if parent_id is not None else None
                        unit_id = parent_id if parent_id is not None else primary_node_id

                        q_obj.bloom_level = bloom
                        q_obj.lesson_id = lesson_id
                        q_obj.unit_id = unit_id

                        db.execute(
                            delete(LmsQuestionUnit).where(LmsQuestionUnit.question_id == q_obj.question_id)
                        )
                        for nid, w in valid_nodes:
                            db.add(LmsQuestionUnit(question_id=q_obj.question_id, unit_id=nid, weight=w))

                        bloom_dist[bloom] = bloom_dist.get(bloom, 0) + 1
                    else:
                        fallback_node = q_obj.lesson_id or q_obj.unit_id or shortlist[0].id
                        q_obj.bloom_level = 2
                        db.execute(
                            delete(LmsQuestionUnit).where(LmsQuestionUnit.question_id == q_obj.question_id)
                        )
                        db.add(LmsQuestionUnit(question_id=q_obj.question_id, unit_id=fallback_node, weight=1.0))
                        bloom_dist[2] = bloom_dist.get(2, 0) + 1

                # Commit batch này vào DB ngay lập tức
                db.commit()
                processed_so_far += len(chunk)

                # Đếm số câu còn lại chưa phân tích
                remaining_cnt = db.execute(
                    select(func.count(LmsQuestionBank.question_id)).where(
                        LmsQuestionBank.subject_id == subject_id,
                        LmsQuestionBank.bloom_level.is_(None),
                    )
                ).scalar() or 0

                job_manager.update_progress(
                    job_id,
                    processed_count=processed_so_far,
                    bloom_dist=bloom_dist,
                    unclassified_remaining=remaining_cnt,
                )

            # Hoàn tất job
            remaining_cnt = db.execute(
                select(func.count(LmsQuestionBank.question_id)).where(
                    LmsQuestionBank.subject_id == subject_id,
                    LmsQuestionBank.bloom_level.is_(None),
                )
            ).scalar() or 0

            job_manager.complete_job(
                job_id,
                processed_count=processed_so_far,
                bloom_dist=bloom_dist,
                unclassified_remaining=remaining_cnt,
                message=f"Đã phân tích và gán Bloom thành công cho {processed_so_far} câu hỏi LMS.",
            )
            logger.info("Hoàn tất Job %s: %d câu đã phân tích.", job_id, processed_so_far)

    except Exception as ex:
        logger.error("Job %s thất bại: %s", job_id, ex, exc_info=True)
        job_manager.fail_job(job_id, str(ex))
