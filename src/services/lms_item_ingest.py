"""src/services/lms_item_ingest.py — Nạp dữ liệu item-response LMS từ đối tác (3 bảng).

Đối tác đổ dữ liệu từng câu trắc nghiệm (Item-Response Matrix). Module này:
1. Chuẩn hóa đầu vào (validate rows) → danh sách ItemIngestRow.
2. Mapping fallback 3 tầng để quy đổi 1 câu về unit_id + bloom_level:
     Tầng 1: Direct (assignment_competencies / course_lesson_id).
     Tầng 2: Strand (stg_so_strand_path) — bổ sung sau khi có dữ liệu strand.
     Tầng 3: AI Classifier (question_classify) — xử lý bất đồng bộ / bên ngoài.
   Module này KHÔNG gọi DB/LLM trực tiếp: nhận người quyết định mapping (mapping_fn)
   để dễ test offline.
3. Logic `is_best_attempt`: khi nạp attempt k, nếu score cao hơn best hiện có thì
   hạ các attempt cũ (is_best_attempt=FALSE) và đánh dấu attempt k TRUE.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

# Ngưỡng đoán mò siêu tốc: đúng câu khó trong < N giây → coi nhiễu/gian lận.
RAPID_GUESS_SECONDS = 2
# Bloom mặc định nếu không xác định được.
DEFAULT_BLOOM = 3

# integrity_flag: 0 Normal | 1 Suspected (nghi nhiễu/gian lận) | 2 Flagged (xác nhận).
INTEGRITY_NORMAL = 0
INTEGRITY_SUSPECTED = 1


class AlreadyExistsError(Exception):
    """Trùng (student, assignment, question, attempt) — vi phạm unique index."""


@dataclass
class ItemIngestRow:
    """1 dòng phản hồi câu hỏi từ đối tác (đã chuẩn hóa)."""

    student_code: str
    assignment_id: int
    question_id: int
    so_school_id: int
    subject_id: int
    attempt_number: int = 1
    is_correct: bool | None = None
    score_received: float | None = None
    max_score: float = 1.0
    response_time_seconds: int | None = None
    attempt_date: str | None = None
    question: str | None = None  # nội dung câu (cho Tầng 3 AI fallback)
    # Ẩn mapping từ ngoài (table → column khác nhau tùy đối tác).
    _raw: dict = field(default_factory=dict, repr=False)


# Mapping function: (row) -> (unit_id | None, bloom_level | None). Dùng cho Tầng 1.
MappingFn = Callable[[ItemIngestRow], tuple[int | None, int | None]]


class UnitMapper(Protocol):
    """Giao diện mapping 3 tầng (do adapter triển khai khi nối DB thật)."""

    def map_unit(self, row: ItemIngestRow) -> tuple[int | None, int | None]:
        """Trả (unit_id, bloom_level) sau 3 tầng; (None, None) nếu không map được."""
        ...


def validate_row(raw: dict) -> ItemIngestRow:
    """Chuẩn hóa 1 dict → ItemIngestRow; raise ValueError nếu thiếu trường bắt buộc."""
    try:
        student = str(raw["student_code"]).strip()
    except (KeyError, TypeError):
        raise ValueError(f"Thiếu student_code: {raw}")
    if not student:
        raise ValueError("student_code rỗng")

    def _int(key, default):
        try:
            v = raw[key]
            return default if v is None else int(v)
        except (KeyError, TypeError, ValueError):
            return default

    return ItemIngestRow(
        student_code=student,
        assignment_id=_int("assignment_id", 0),
        question_id=_int("question_id", 0),
        so_school_id=_int("so_school_id", 0),
        subject_id=_int("subject_id", 0),
        attempt_number=_int("attempt_number", 1),
        is_correct=raw.get("is_correct"),
        score_received=float(raw["score_received"]) if raw.get("score_received") is not None else None,
        max_score=float(raw.get("max_score", 1.0)) or 1.0,
        response_time_seconds=_int("response_time_seconds", None),
        attempt_date=raw.get("attempt_date"),
        question=raw.get("question"),
        _raw=raw,
    )


def resolve_integrity(row: ItemIngestRow) -> int:
    """Gán integrity_flag dựa trên hành vi: đoán mò siêu tốc → Suspected."""
    if row.response_time_seconds is not None and row.response_time_seconds > 0:
        if row.response_time_seconds < RAPID_GUESS_SECONDS:
            return INTEGRITY_SUSPECTED
    return INTEGRITY_NORMAL


def resolve_mastery(
    unit_mapper: UnitMapper,
    mappable: MappingFn,
    row: ItemIngestRow,
) -> tuple[int | None, int | None]:
    """Mapping 3 tầng: Tầng1 direct qua mappable → Tầng2/3 qua unit_mapper.

    Trả (unit_id, bloom_level), (None, None) nếu không map được.
    """
    # Tầng 1: Direct mapping (assignment_competencies / course_lesson_id).
    unit, bloom = mappable(row)
    if unit is not None:
        return unit, bloom if bloom is not None else DEFAULT_BLOOM
    # Tầng 2 + 3: strand hoặc AI classifier (do adapter triển khai).
    unit2, bloom2 = unit_mapper.map_unit(row)
    return unit2, bloom2 if bloom2 is not None else DEFAULT_BLOOM


def deduplicate_rows(rows: list[ItemIngestRow]) -> dict[tuple, ItemIngestRow]:
    """Dedup theo (student, assignment, question, attempt) giữ best score; chiều lịch sử riêng."""
    seen: dict[tuple, ItemIngestRow] = {}
    for r in rows:
        key = (r.student_code, r.assignment_id, r.question_id, r.attempt_number)
        cur = seen.get(key)
        if cur is None:
            seen[key] = r
            continue
        # Giữ bản có score cao hơn (best attempt trong cùng lần).
        s_new = r.score_received if r.score_received is not None else 0.0
        s_cur = cur.score_received if cur.score_received is not None else 0.0
        if s_new > s_cur:
            seen[key] = r
    return seen


def build_best_attempt_flags(
    rows: list[ItemIngestRow],
) -> dict[tuple, ItemIngestRow]:
    """Xác định is_best_attempt cho từng (student, assignment, question) theo PRO-TIP.

    Trả dict {(student, assignment, question): row_best} — chỉ 1 best/1 (s,a,q).
    Chỉ tính cho attempt cao nhất điểm. (Muốn lưu cả history → gọi riêng.)
    """
    best: dict[tuple, ItemIngestRow] = {}
    for r in rows:
        key = (r.student_code, r.assignment_id, r.question_id)
        cur = best.get(key)
        s_new = r.score_received if r.score_received is not None else 0.0
        s_cur = cur.score_received if cur is not None and cur.score_received is not None else 0.0
        if cur is None or s_new > s_cur:
            best[key] = r
    return best
