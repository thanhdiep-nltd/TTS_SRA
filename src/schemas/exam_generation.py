"""DTO cho tính năng tạo đề chính thức từ ngân hàng câu hỏi (AI Exam Generation).

Xem docs/exam_generation_design.md. Tầng schemas (Pydantic) — không chứa logic DB.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models import enums
from src.schemas.common import ORMBase

# ----------------------------- Ngân hàng câu hỏi -----------------------------


class QuestionItemCreate(BaseModel):
    """Tạo câu hỏi thủ công (source=MANUAL). Câu sinh bằng LLM dùng luồng riêng (Phase 2)."""

    subject_id: UUID
    grade_number: int = Field(ge=1, le=12)
    unit_id: UUID
    bloom_level: int = Field(ge=1, le=6)
    question_type: enums.QuestionType
    stem: str = Field(min_length=1)
    options: list[dict] | None = None  # [{key, text}]
    answer_key: dict
    solution: str | None = None
    default_points: float = Field(default=1.0, gt=0)


class QuestionItemUpdate(BaseModel):
    """Sửa câu (chỉ khi DRAFT/REVIEW). Mọi field tùy chọn."""

    stem: str | None = None
    options: list[dict] | None = None
    answer_key: dict | None = None
    solution: str | None = None
    bloom_level: int | None = Field(default=None, ge=1, le=6)
    default_points: float | None = Field(default=None, gt=0)


class ReviewDecision(BaseModel):
    """Quyết định duyệt câu hỏi (Trưởng bộ môn/ADMIN)."""

    approve: bool
    reason: str | None = None  # bắt buộc về mặt nghiệp vụ khi từ chối (kiểm ở service)


class GenerateItemsRequest(BaseModel):
    """Sinh câu DRAFT bằng LLM+RAG cho 1 ô (môn, khối, chuẩn CT, Bloom, loại câu)."""

    subject_id: UUID
    grade_number: int = Field(ge=1, le=12)
    unit_id: UUID
    bloom_level: int = Field(ge=1, le=6)
    question_type: enums.QuestionType
    count: int = Field(default=5, ge=1, le=20)


class QuestionItemRead(ORMBase):
    id: UUID
    subject_id: UUID
    grade_number: int
    unit_id: UUID
    bloom_level: int
    question_type: enums.QuestionType
    stem: str
    options: list[dict] | None
    solution: str | None
    default_points: float
    status: enums.ItemStatus
    source: enums.ItemSource
    times_used: int
    p_value: float | None
    exposure_at: datetime | None
    created_at: datetime
    created_by: UUID
    created_by_name: str
    reviewed_by: UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    provenance: dict  # {model, rag_sources, rag_hits, self_consistency} — KHÔNG chứa đáp án, an toàn hiện ở list


class QuestionItemDetail(QuestionItemRead):
    """Có kèm đáp án — chỉ trả cho người ra đề/duyệt (không lộ cho HS)."""

    answer_key: dict


class QuestionItemListPage(BaseModel):
    """Trang kết quả danh sách câu hỏi (phân trang — kho có thể lên tới hàng trăm câu/môn+khối)."""

    items: list[QuestionItemRead]
    total: int


class CalibrationRow(BaseModel):
    """Một dòng bảng hiệu chỉnh kho câu: thống kê thực nghiệm + cờ 'bệnh' + khuyến nghị."""

    item_id: UUID
    stem: str
    bloom_level: int
    status: enums.ItemStatus
    times_used: int
    p_value: float | None
    discrimination: float | None
    flags: list[str]
    recommendation: str | None  # RETIRE | REVIEW | None


# ----------------------------- Ma trận đề (blueprint) -----------------------------


class BlueprintCell(BaseModel):
    """Một ô ma trận: cần bao nhiêu câu của (chuẩn CT, Bloom, loại câu) và mỗi câu mấy điểm."""

    unit_id: UUID
    bloom_level: int = Field(ge=1, le=6)
    question_type: enums.QuestionType
    num_questions: int = Field(ge=1, le=100)
    points_each: float = Field(gt=0)


class BlueprintCreate(BaseModel):
    subject_id: UUID
    grade_number: int = Field(ge=1, le=12)
    score_category: enums.ScoreCategory  # chỉ MIDTERM/FINAL (kiểm ở service)
    title: str = Field(min_length=1, max_length=255)
    total_points: float = Field(default=10.0, gt=0)
    duration_min: int | None = Field(default=None, ge=1)
    target_difficulty: float | None = Field(default=None, ge=0, le=1)
    cells: list[BlueprintCell] = Field(min_length=1)


class BlueprintUpdate(BaseModel):
    """Tinh chỉnh ma trận đã tạo. Mọi field tùy chọn; Σ điểm được re-validate ở service."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    total_points: float | None = Field(default=None, gt=0)
    duration_min: int | None = Field(default=None, ge=1)
    target_difficulty: float | None = Field(default=None, ge=0, le=1)
    cells: list[BlueprintCell] | None = Field(default=None, min_length=1)


class BlueprintRead(ORMBase):
    id: UUID
    subject_id: UUID
    grade_number: int
    score_category: enums.ScoreCategory
    title: str
    total_points: float
    duration_min: int | None
    target_difficulty: float | None
    cells: list[dict]
    exam_format: enums.ExamFormat | None  # suy ra từ cells khi lưu, không do client set
    created_at: datetime


# ----------------------------- Đối chiếu kho khi soạn ma trận -----------------------------


class CoverageCellRequest(BaseModel):
    """Một ô cần kiểm tra kho có đủ câu APPROVED không (chưa cần lưu blueprint)."""

    unit_id: UUID
    bloom_level: int = Field(ge=1, le=6)
    question_type: enums.QuestionType
    num_questions: int = Field(ge=1, le=100)


class CoverageRequest(BaseModel):
    subject_id: UUID
    grade_number: int = Field(ge=1, le=12)
    cells: list[CoverageCellRequest] = Field(min_length=1)


class CoverageCellResult(BaseModel):
    unit_id: UUID
    bloom_level: int
    question_type: enums.QuestionType
    needed: int
    available: int
    shortfall: int


# ----------------------------- Gợi ý ma trận (recommendation) -----------------------------


class RecommendBlueprintRequest(BaseModel):
    """GV chọn phạm vi chương đã học + loại đề + quy mô; hệ gợi ý phần còn lại từ năng lực
    thực tế của trường (đơn vị, mức Bloom, điểm mỗi câu)."""

    subject_id: UUID
    grade_number: int = Field(ge=1, le=12)
    grade_id: UUID  # để đọc năng lực khối (content_adjusted_ability)
    semester_id: UUID
    score_category: enums.ScoreCategory  # chỉ MIDTERM/FINAL (kiểm ở router)
    unit_ids: list[UUID] = Field(min_length=1)
    total_points: float = Field(default=10.0, gt=0)
    exam_format: enums.ExamFormat
    total_questions: int = Field(ge=1, le=200)
    mix_mcq_ratio: float = Field(default=0.7, ge=0.3, le=0.9)  # chỉ áp dụng khi exam_format=MIXED


class RecommendCellDraft(BaseModel):
    """Một ô ma trận do hệ gợi ý — GV xem/chỉnh rồi mới lưu qua POST /exam-blueprints."""

    unit_id: UUID
    unit_name: str
    bloom_level: int
    question_type: enums.QuestionType
    num_questions: int
    points_each: float
    available: int
    shortfall: int


class BlueprintDraft(BaseModel):
    """Bản nháp ma trận — KHÔNG ghi DB. GV chỉnh cells rồi POST /exam-blueprints để lưu thật."""

    subject_id: UUID
    grade_number: int
    target_difficulty: float
    ability_used: float
    expected_cdi: float | None
    cells: list[RecommendCellDraft]
    rationale: list[str]


# ----------------------------- Ráp đề -----------------------------


class AssembleRequest(BaseModel):
    blueprint_id: UUID
    semester_id: UUID
    grade_id: UUID
    num_variants: int = Field(default=1, ge=1, le=20)


class AssembledItemRead(BaseModel):
    position: int
    item_id: UUID
    points: float
    stem: str
    question_type: enums.QuestionType
    options: list[dict] | None  # đã xáo thứ tự (option_order áp dụng)


class VariantRead(BaseModel):
    variant_code: str
    items: list[AssembledItemRead]


class GeneratedExamRead(ORMBase):
    id: UUID
    blueprint_id: UUID
    semester_id: UUID
    grade_id: UUID | None
    num_variants: int
    status: enums.GenExamStatus
    exam_paper_id: UUID | None
    created_at: datetime


class GeneratedExamDetail(GeneratedExamRead):
    variants: list[VariantRead]


# ----------------------------- Đáp án (chỉ người ra đề/duyệt) -----------------------------


class AnswerKeyItemRead(BaseModel):
    position: int
    item_id: UUID
    points: float
    answer_key: dict
    solution: str | None


class VariantAnswerRead(BaseModel):
    variant_code: str
    items: list[AnswerKeyItemRead]
