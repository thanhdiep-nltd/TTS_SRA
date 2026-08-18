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
    description: str | None = None


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


class IngestedChapterRead(BaseModel):
    """1 chương (node level 1) phát hiện từ mục lục sách, kèm bài con."""

    code: str
    name: str
    semester_number: int | None = None
    lessons: list[IngestedLessonRead] = []


class BookIngestResult(BaseModel):
    """Kết quả nạp sách giáo khoa → tự tách mục lục thành node chương/bài."""

    subject_code: str
    grade: int
    semester: int | None = None
    source: str
    chapters: list[IngestedChapterRead]
    inserted: int
    updated: int
    hidden_placeholders: int
    dry_run: bool = False
