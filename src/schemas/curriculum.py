"""DTO cho API admin quản lý catalog chuẩn chương trình (bảng phẳng — không RAG)."""

from pydantic import BaseModel


class CurriculumUnitRead(BaseModel):
    """1 node chương/bài trong bảng phẳng curriculum_units."""

    id: int
    code: str
    name: str
    grade_number: int
    semester_number: int | None = None
    parent_id: int | None = None
    parent_name: str | None = None
    is_active: bool = True
    is_phu: bool = False
    description: str | None = None
    # Làm giàu nội dung khi nạp sách (quét toàn cuốn): tóm tắt, từ khóa, mục con.
    summary: str | None = None
    keywords: list[str] | None = None
    sections: list[dict] | None = None
    book_id: int | None = None
    book_title: str | None = None


class CurriculumUploadResult(BaseModel):
    """Kết quả upload mục lục (JSON/markdown) → ghi thẳng curriculum_units."""

    subject_code: str
    source: str
    grades: list[int]
    inserted: int
    updated: int
    hidden_placeholders: int


class IngestedLessonRead(BaseModel):
    """1 bài con (node level 2) phát hiện từ mục lục sách, kèm nội dung làm giàu."""

    code: str
    name: str
    is_phu: bool = False
    summary: str | None = None
    keywords: list[str] | None = None
    sections: list[dict] | None = None


class IngestedChapterRead(BaseModel):
    """1 chương (node level 1) phát hiện từ mục lục sách, kèm bài con + nội dung làm giàu."""

    code: str
    name: str
    semester_number: int | None = None
    is_phu: bool = False
    summary: str | None = None
    keywords: list[str] | None = None
    sections: list[dict] | None = None
    lessons: list[IngestedLessonRead] = []


class BookIngestResult(BaseModel):
    """Kết quả nạp sách giáo khoa → tự tách mục lục thành node chương/bài."""

    subject_code: str
    grade: int
    semester: int | None = None
    source: str
    chapters: list[IngestedChapterRead]
    inserted: int = 0
    updated: int = 0
    hidden_placeholders: int = 0
    warnings: list[str] = []
    dry_run: bool = False
    book_title: str | None = None
    book_id: int | None = None


class BookIngestJobRead(BaseModel):
    """Trạng thái job nạp sách bất đồng bộ (DB-backed queue — giống EWS predict)."""

    job_id: int
    status: str  # pending | processing | completed | failed
    progress: int = 0
    subject_code: str
    grade_number: int
    semester_number: int | None = None
    filename: str | None = None
    book_title: str | None = None
    vlm_model: str | None = None
    result: BookIngestResult | None = None
    error: str | None = None
    created_at: str | None = None


class CurriculumBookRead(BaseModel):
    """1 cuốn SGK đã nạp, kèm số node chương/bài thuộc cuốn."""

    id: int
    title: str
    subject_code: str
    subject_id: int
    grade_number: int
    semester_number: int | None = None
    school_year_id: int | None = None
    school_year_name: str | None = None
    is_locked: bool = False
    filename: str | None = None
    source: str | None = None
    unit_count: int = 0
    created_at: str | None = None


class SchoolYearRead(BaseModel):
    """Năm học học đường (s360.dim_school_year)."""

    id: int
    code: str
    fullname: str
    is_current: bool = False
    is_locked: bool = False


class TeachingScheduleRead(BaseModel):
    """1 tuần trong phân phối chương trình môn học."""

    id: int
    school_year_id: int
    subject_id: int
    grade_number: int
    semester_number: int
    week_number: int
    unit_id: int | None = None
    unit_code: str | None = None
    unit_name: str | None = None
    topic: str | None = None
    num_periods: int = 2
    notes: str | None = None


class BookLockToggleResult(BaseModel):
    """Kết quả khóa/mở khóa cuốn sách giáo khoa."""

    book_id: int
    title: str
    is_locked: bool
    message: str


class BookDeleteResult(BaseModel):
    """Kết quả xóa cuốn sách giáo khoa và các node liên quan."""

    book_id: int
    title: str
    deleted_units_count: int


class BookClearEnrichmentResult(BaseModel):
    """Kết quả xóa sạch dữ liệu làm giàu (tóm tắt/từ khóa/mục con) của một cuốn sách."""

    book_id: int
    title: str
    cleared_units_count: int
    message: str


class BookReEnrichRequest(BaseModel):
    """Tham số khi yêu cầu chạy lại bước làm giàu nội dung cho một cuốn sách."""

    vlm_model: str | None = None



