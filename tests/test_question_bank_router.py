"""Test offline cho helper map ORM -> schema trong api/v1/question_bank.py.

Bug thật phát hiện qua kiểm thử trình duyệt: _to_read() validate thẳng ORM object vào
QuestionItemRead (yêu cầu created_by_name/reviewed_by_name) TRƯỚC khi gắn 2 field này
vào -> pydantic.ValidationError -> 500 ở GET /question-bank/items. Test này khóa lại hành vi đúng.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from src.api.v1 import question_bank
from src.models import enums


def _question_item(**overrides):
    base = {
        "id": uuid4(),
        "subject_id": uuid4(),
        "grade_number": 8,
        "unit_id": uuid4(),
        "bloom_level": 2,
        "question_type": enums.QuestionType.MCQ,
        "stem": "1 + 1 = ?",
        "options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        "answer_key": {"correct": "B"},
        "solution": "...",
        "default_points": 1.0,
        "status": enums.ItemStatus.DRAFT,
        "source": enums.ItemSource.MANUAL,
        "times_used": 0,
        "p_value": None,
        "exposure_at": None,
        "created_at": datetime.now(UTC),
        "created_by": uuid4(),
        "reviewed_by": None,
        "reviewed_at": None,
        "provenance": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_to_read_builds_without_orm_having_name_fields():
    """ORM object KHÔNG có created_by_name/reviewed_by_name — _to_read phải tự gắn vào, không crash."""
    item = _question_item()
    names = {item.created_by: "Nguyễn Văn A"}

    result = question_bank._to_read(item, names)

    assert result.created_by_name == "Nguyễn Văn A"
    assert result.reviewed_by_name is None
    assert result.id == item.id


def test_to_read_falls_back_when_creator_name_missing():
    item = _question_item()
    result = question_bank._to_read(item, names={})
    assert result.created_by_name == "?"


def test_to_read_includes_reviewer_name_when_reviewed():
    reviewer_id = uuid4()
    item = _question_item(reviewed_by=reviewer_id, status=enums.ItemStatus.APPROVED)
    names = {item.created_by: "GV A", reviewer_id: "Trưởng BM B"}

    result = question_bank._to_read(item, names)

    assert result.reviewed_by_name == "Trưởng BM B"


def test_to_detail_includes_answer_key():
    item = _question_item(answer_key={"correct": "B"})
    result = question_bank._to_detail(item, names={item.created_by: "GV A"})
    assert result.answer_key == {"correct": "B"}
    assert result.created_by_name == "GV A"


def test_to_read_strips_stem_embedding_from_provenance():
    """stem_embedding chỉ dùng nội bộ cho dedup (_existing_embeddings) — KHÔNG được lộ ra API response."""
    item = _question_item(
        provenance={
            "model": "gpt-4o-mini",
            "rag_sources": ["sgk_toan_8.pdf"],
            "stem_embedding": [0.1, 0.2, 0.3],
        }
    )
    result = question_bank._to_read(item, names={})
    assert "stem_embedding" not in result.provenance
    assert result.provenance == {"model": "gpt-4o-mini", "rag_sources": ["sgk_toan_8.pdf"]}


def test_to_read_leaves_provenance_untouched_when_no_embedding():
    item = _question_item(provenance={"model": "gpt-4o-mini", "critic": {"ok": True}})
    result = question_bank._to_read(item, names={})
    assert result.provenance == {"model": "gpt-4o-mini", "critic": {"ok": True}}


def test_user_names_skips_none_ids():
    class _FakeDB:
        def execute(self, _stmt):
            class _R:
                def all(self):
                    return []

            return _R()

    assert question_bank._user_names(_FakeDB(), {None}) == {}
