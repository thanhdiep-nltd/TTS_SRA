"""Test offline cho công cụ test 1 câu hỏi (tab "Kiểm tra câu hỏi" — TEVI).

Không gọi LLM/VLM thật, không chạm Neon. File tạm cho test PDF ghi vào temp/ (tránh
tmp_path của pytest bị chặn trong một số sandbox).
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import fitz
import pytest
from sqlalchemy.orm import Session

from src.api import deps
from src.api.v1 import question_classify as qc_api
from src.main import app
from src.models.enums import FileType
from src.models.tables import CurriculumUnit
from src.schemas.question_classify import ClassifiedItem, QuestionClassifyResult
from src.services import question_classify as qc
from src.services.vlm import VlmUnavailableError

_TEMP_DIR = Path(__file__).resolve().parents[1] / "temp"


def _fake_llm_response(content: str):
    return SimpleNamespace(content=content)


def _unit(unit_id, code, name, grade=6, semester=1, parent_id=None):
    return CurriculumUnit(
        id=unit_id,
        subject_id=106,
        grade_number=grade,
        parent_id=parent_id,
        code=code,
        name=name,
        semester_number=semester,
        is_active=True,
    )


def _write_temp_pdf(name: str) -> Path:
    _TEMP_DIR.mkdir(exist_ok=True)
    path = _TEMP_DIR / name
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path


# ---------- classify_question ----------


def test_classify_question_maps_chapter_and_lesson():
    chapter = _unit(1, "TOAN6_C1", "So tu nhien")
    lesson = _unit(2, "TOAN6_C1_U1", "Tap hop", parent_id=1)
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '[{"topic":"Cau hoi","nodes":[{"node_id":2,"weight":1.0}],"bloom_level":2,'
        '"off_curriculum_weight":0.0,"confidence":0.9,"excerpt":"2/3 + 1/4"}]'
    )
    result = qc.classify_question("Cau hoi: 2/3 + 1/4 bang bao nhieu?", [chapter, lesson], llm=mock_llm)
    assert result.matched is True
    assert result.off_curriculum is False
    assert result.items[0].chapter == "So tu nhien"
    assert result.items[0].lesson == "Tap hop"
    assert result.items[0].unit_code == "TOAN6_C1_U1"
    assert result.items[0].bloom_level == 2
    assert result.items[0].weight == pytest.approx(1.0)
    assert result.items[0].confidence == pytest.approx(0.9)


def test_classify_question_maps_multiple_nodes_sorted_by_weight():
    chapter = _unit(1, "TOAN6_C1", "So tu nhien")
    lesson = _unit(2, "TOAN6_C1_U1", "Tap hop", parent_id=1)
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '[{"topic":"Cau hoi","nodes":[{"node_id":1,"weight":0.3},{"node_id":2,"weight":0.7}],'
        '"bloom_level":3,"off_curriculum_weight":0.0}]'
    )
    result = qc.classify_question("Cau hoi ket hop", [chapter, lesson], llm=mock_llm)
    assert result.matched is True
    assert [it.unit_code for it in result.items] == ["TOAN6_C1_U1", "TOAN6_C1"]
    assert result.items[0].weight == pytest.approx(0.7)


def test_classify_question_off_curriculum_returns_candidates():
    units = [_unit(1, "A", "Tap hop"), _unit(2, "B", "So nguyen"), _unit(3, "C", "Phan so")]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '[{"topic":"Cau hoi","nodes":[],"bloom_level":3,"off_curriculum_weight":1.0}]'
    )
    result = qc.classify_question("Cau hoi ngoai chuong trinh", units, llm=mock_llm)
    assert result.matched is False
    assert result.off_curriculum is True
    assert result.items == []
    assert result.candidates == ["Tap hop", "So nguyen", "Phan so"]


def test_classify_question_too_short_skips_llm():
    mock_llm = MagicMock()
    result = qc.classify_question("1+1=?", [_unit(1, "A", "Tap hop")], llm=mock_llm)
    assert result.matched is False
    mock_llm.invoke.assert_not_called()


# ---------- extract_question_text ----------


def test_extract_question_text_image_uses_vlm(monkeypatch):
    p = _TEMP_DIR / "_test_question.png"
    _TEMP_DIR.mkdir(exist_ok=True)
    p.write_bytes(b"\x89PNG fake")
    try:
        monkeypatch.setattr(qc.vlm, "read_image_bytes", lambda data, **k: "Cau 1: $x^2=4$")
        assert qc.extract_question_text(p, FileType.IMAGE) == "Cau 1: $x^2=4$"
    finally:
        p.unlink(missing_ok=True)


def test_extract_question_text_pdf_caps_pages(monkeypatch):
    pdf = _write_temp_pdf("_test_question.pdf")
    try:
        captured: dict = {}

        def fake_read(path, start_page=None, end_page=None, **k):
            captured["end"] = end_page
            return "Cau PDF"

        monkeypatch.setattr(qc.vlm, "read_pdf_pages_range", fake_read)
        assert qc.extract_question_text(pdf, FileType.PDF) == "Cau PDF"
        assert captured["end"] == 1  # PDF chỉ 1 trang
    finally:
        pdf.unlink(missing_ok=True)


def test_extract_question_text_rejects_word():
    with pytest.raises(ValueError, match="Chỉ hỗ trợ ảnh hoặc PDF"):
        qc.extract_question_text(Path("cau_hoi.docx"), FileType.WORD)


# ---------- resolve_shortlist ----------


def test_resolve_shortlist_missing_subject(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(qc.curriculum_catalog, "resolve_subject_ids", lambda db_, code, grades: {})
    with pytest.raises(ValueError, match="chưa có trong danh mục"):
        qc.resolve_shortlist(db, "TOAN_6", 6)


def test_resolve_shortlist_no_books(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(qc.curriculum_catalog, "resolve_subject_ids", lambda db_, code, grades: {6: 106})
    monkeypatch.setattr(qc.content_difficulty, "build_shortlist", lambda *a, **k: [])
    with pytest.raises(ValueError, match="chưa nạp SGK"):
        qc.resolve_shortlist(db, "TOAN_6", 6)


# ---------- Endpoint POST /exam-difficulty/classify-question ----------


@pytest.fixture
def question_client(client):
    """Ghi đè auth + db (mock) cho endpoint test — không chạm Neon."""
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=1, so_school_id=1, role="SUBJECT_TEACHER", is_active=True
    )
    app.dependency_overrides[deps.get_db] = lambda: MagicMock(spec=Session)
    yield client
    app.dependency_overrides.clear()


def _patch_pipeline(monkeypatch, *, text="Cau hoi: 2/3 + 1/4", result=None):
    """Mock toàn bộ chuỗi xử lý: lưu file → shortlist → VLM → LLM."""
    monkeypatch.setattr(qc_api.storage, "save_exam_file", lambda file: ("stored.png", 10, FileType.IMAGE))
    monkeypatch.setattr(qc_api.storage, "delete_exam_file", lambda stored: None)
    monkeypatch.setattr(qc_api.question_classify, "resolve_shortlist", lambda db, code, grade: [_unit(1, "A", "Tap hop")])
    monkeypatch.setattr(qc_api.question_classify, "extract_question_text", lambda path, ft: text)
    monkeypatch.setattr(
        qc_api.question_classify,
        "classify_question",
        lambda t, shortlist: result
        or QuestionClassifyResult(
            text=t,
            matched=True,
            off_curriculum=False,
            items=[
                ClassifiedItem(
                    topic="Cau hoi",
                    chapter="So tu nhien",
                    lesson="Tap hop",
                    unit_code="TOAN6_C1_U1",
                    unit_name="Tap hop",
                    bloom_level=2,
                    weight=1.0,
                    confidence=0.9,
                    excerpt=None,
                )
            ],
        ),
    )


@pytest.mark.asyncio
async def test_classify_question_endpoint_returns_chapter(question_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    res = await question_client.post(
        "/api/v1/exam-difficulty/classify-question",
        data={"subject_code": "TOAN_6", "grade_number": "6"},
        files={"file": ("cau_hoi.png", b"\x89PNG fake", "image/png")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["matched"] is True
    assert body["items"][0]["chapter"] == "So tu nhien"
    assert body["items"][0]["lesson"] == "Tap hop"
    assert "Cau hoi" in body["text"]


@pytest.mark.asyncio
async def test_classify_question_endpoint_rejects_unsupported_file(question_client, monkeypatch):
    monkeypatch.setattr(
        qc_api.storage,
        "save_exam_file",
        lambda file: (_ for _ in ()).throw(ValueError("Định dạng không hỗ trợ: .xyz")),
    )
    res = await question_client.post(
        "/api/v1/exam-difficulty/classify-question",
        data={"subject_code": "TOAN_6", "grade_number": "6"},
        files={"file": ("cau_hoi.xyz", b"abc", "text/plain")},
    )
    assert res.status_code == 400
    assert "Định dạng không hỗ trợ" in res.json()["detail"]


@pytest.mark.asyncio
async def test_classify_question_endpoint_rejects_word(question_client, monkeypatch):
    monkeypatch.setattr(qc_api.storage, "save_exam_file", lambda file: ("stored.docx", 10, FileType.WORD))
    monkeypatch.setattr(qc_api.storage, "delete_exam_file", lambda stored: None)
    res = await question_client.post(
        "/api/v1/exam-difficulty/classify-question",
        data={"subject_code": "TOAN_6", "grade_number": "6"},
        files={"file": ("cau_hoi.docx", b"doc", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res.status_code == 400
    assert "Chỉ hỗ trợ ảnh hoặc PDF" in res.json()["detail"]


@pytest.mark.asyncio
async def test_classify_question_endpoint_422_when_no_sgk(question_client, monkeypatch):
    monkeypatch.setattr(qc_api.storage, "save_exam_file", lambda file: ("stored.png", 10, FileType.IMAGE))
    monkeypatch.setattr(qc_api.storage, "delete_exam_file", lambda stored: None)
    monkeypatch.setattr(
        qc_api.question_classify,
        "resolve_shortlist",
        lambda db, code, grade: (_ for _ in ()).throw(ValueError("Môn TOAN_6 khối 6 chưa nạp SGK — hãy nạp sách trước.")),
    )
    res = await question_client.post(
        "/api/v1/exam-difficulty/classify-question",
        data={"subject_code": "TOAN_6", "grade_number": "6"},
        files={"file": ("cau_hoi.png", b"\x89PNG fake", "image/png")},
    )
    assert res.status_code == 422
    assert "chưa nạp SGK" in res.json()["detail"]


@pytest.mark.asyncio
async def test_classify_question_endpoint_503_when_vlm_down(question_client, monkeypatch):
    monkeypatch.setattr(qc_api.storage, "save_exam_file", lambda file: ("stored.png", 10, FileType.IMAGE))
    monkeypatch.setattr(qc_api.storage, "delete_exam_file", lambda stored: None)
    monkeypatch.setattr(qc_api.question_classify, "resolve_shortlist", lambda db, code, grade: [_unit(1, "A", "Tap hop")])
    monkeypatch.setattr(
        qc_api.question_classify,
        "extract_question_text",
        lambda path, ft: (_ for _ in ()).throw(VlmUnavailableError("Máy chủ AI hiện quá tải (HTTP 503).")),
    )
    res = await question_client.post(
        "/api/v1/exam-difficulty/classify-question",
        data={"subject_code": "TOAN_6", "grade_number": "6"},
        files={"file": ("cau_hoi.png", b"\x89PNG fake", "image/png")},
    )
    assert res.status_code == 503
    assert "quá tải" in res.json()["detail"]
