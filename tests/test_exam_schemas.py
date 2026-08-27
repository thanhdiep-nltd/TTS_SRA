from datetime import UTC, datetime
from types import SimpleNamespace

from src.models.enums import FileType
from src.schemas.exam import ExamPaperDetailRead


def test_exam_paper_detail_read_includes_ai_analysis():
    paper = SimpleNamespace(
        id=1,
        subject_id=1,
        semester_id=1,
        grade_id=None,
        title="De kiem tra Toan 6",
        description=None,
        file_type=FileType.PDF,
        file_size_bytes=1234,
        uploaded_by=1,
        created_at=datetime.now(UTC),
        content_difficulty=0.42,
        content_analyzed_at=datetime.now(UTC),
        ai_analysis={"content_analysis": {"version": 1}},
    )

    result = ExamPaperDetailRead.model_validate(paper)

    assert result.ai_analysis == {"content_analysis": {"version": 1}}
