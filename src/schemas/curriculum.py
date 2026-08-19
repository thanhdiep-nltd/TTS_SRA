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
    """1 bài con (node level 2) phát hiện từ mục lục sách."""

    code: str
    name: str
    is_phu: bool = False


class IngestedChapterRead(BaseModel):
    """1 chương (node level 1) phát hiện từ mục lục sách, kèm bài con."""

    code: str
    name: str
    semester_number: int | None = None
    is_phu: bool = False
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
    filename: str | None = None
    source: str | None = None
    unit_count: int = 0
    created_at: str | None = None
