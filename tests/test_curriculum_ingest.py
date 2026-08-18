"""Test offline cho src/services/curriculum_ingest.py — nạp sách (PDF/DOCX/TXT) tự tách TOC."""

import pytest

from src.services.curriculum_ingest import (
    build_unit_specs_from_toc,
    detect_semester_from_filename,
    extract_toc_from_text,
    ingest_book,
    save_catalog_from_preview,
    upsert_unit_tree,
)

_MD_TOC = """# Mục lục
## LỚP 6
Chương I: Số tự nhiên
Bài 1: Tập hợp
Bài 2: Tập hợp số tự nhiên
Chương II: Số nguyên
Bài 1: Số nguyên âm
"""


class _FakeDb:
    """Fake session ghi nhận spec được upsert — không chạm DB thật."""

    def __init__(self):
        self.seen: list[dict] = []
        self.committed = False

    def execute(self, stmt):
        return _FakeResult(self)

    def add(self, obj):
        obj.id = 100 + len(self.seen)
        self.seen.append(
            {
                "id": obj.id,
                "code": obj.code,
                "name": obj.name,
                "parent_id": obj.parent_id,
                "semester_number": obj.semester_number,
            }
        )

    def flush(self):
        return None

    def commit(self):
        self.committed = True


class _FakeResult:
    def __init__(self, db):
        self.db = db

    def scalars(self):
        return self

    def first(self):
        return None

    def all(self):
        return []


def test_detect_semester_from_filename():
    assert detect_semester_from_filename("toan6_tap1.pdf") == 1
    assert detect_semester_from_filename("Toan 6 Tập 2.pdf") == 2
    assert detect_semester_from_filename("toan6-hk1.pdf") == 1
    assert detect_semester_from_filename("toan6.pdf") is None


def test_extract_toc_from_text():
    entries = extract_toc_from_text(_MD_TOC)
    chapters = [e for e in entries if e[0] == 1]
    lessons = [e for e in entries if e[0] == 2]
    assert len(chapters) == 2
    assert chapters[0][1] == "Số tự nhiên"
    assert chapters[1][1] == "Số nguyên"
    assert len(lessons) == 3
    assert lessons[0][1] == "Tập hợp"


def test_build_unit_specs_from_toc_chapters_only():
    entries = extract_toc_from_text(_MD_TOC)
    specs = build_unit_specs_from_toc(entries, "toan", 6, 1, include_lessons=False)
    assert [s["code"] for s in specs] == ["TOAN6_C1", "TOAN6_C2"]
    assert specs[0]["semester_number"] == 1
    assert all(s["parent_code"] is None for s in specs)


def test_build_unit_specs_from_toc_with_lessons():
    entries = extract_toc_from_text(_MD_TOC)
    specs = build_unit_specs_from_toc(entries, "toan", 6, 2, include_lessons=True)
    codes = [s["code"] for s in specs]
    assert codes == ["TOAN6_C1", "TOAN6_C1_B1", "TOAN6_C1_B2", "TOAN6_C2", "TOAN6_C2_B1"]
    assert specs[1]["parent_code"] == "TOAN6_C1"
    assert specs[4]["parent_code"] == "TOAN6_C2"


def test_upsert_unit_tree_links_parents():
    entries = extract_toc_from_text(_MD_TOC)
    specs = build_unit_specs_from_toc(entries, "toan", 6, 1, include_lessons=True)
    db = _FakeDb()
    inserted, updated = upsert_unit_tree(db, specs, subject_id=42, grade=6)
    assert inserted == 5
    assert updated == 0
    assert db.committed
    lesson = next(s for s in db.seen if s["code"] == "TOAN6_C1_B1")
    chapter = next(s for s in db.seen if s["code"] == "TOAN6_C1")
    assert lesson["parent_id"] == chapter["id"]


def test_ingest_book_dry_run_no_db_write():
    db = _FakeDb()
    result = ingest_book(db, "toan6_tap1.txt", _MD_TOC.encode(), "toan", 6, dry_run=True)
    assert result["dry_run"] is True
    assert result["source"] == "text"
    assert result["semester"] == 1  # từ tên file
    assert len(result["chapters"]) == 2
    assert result["inserted"] == 0
    assert db.committed is False


def test_ingest_book_text_with_lessons(monkeypatch):
    from src.services import curriculum_ingest

    monkeypatch.setattr(
        curriculum_ingest, "resolve_subject_ids", lambda db, code, grades: {6: 42}
    )
    db = _FakeDb()
    result = ingest_book(
        db, "toan6.txt", _MD_TOC.encode(), "toan", 6, include_lessons=True, dry_run=False
    )
    assert result["dry_run"] is False
    assert len(result["chapters"]) == 2
    assert len(result["chapters"][0]["lessons"]) == 2
    assert result["source"] == "text"


def test_ingest_book_missing_subject_raises(monkeypatch):
    from src.services import curriculum_ingest

    monkeypatch.setattr(curriculum_ingest, "resolve_subject_ids", lambda db, code, grades: {})
    with pytest.raises(ValueError):
        ingest_book(_FakeDb(), "toan6.txt", _MD_TOC.encode(), "toan", 6, dry_run=False)


def test_ingest_book_invalid_extension():
    with pytest.raises(ValueError):
        ingest_book(_FakeDb(), "book.exe", b"data", "toan", 6)


def test_ingest_book_empty_toc_raises():
    with pytest.raises(ValueError):
        ingest_book(_FakeDb(), "book.txt", b"no toc here", "toan", 6)


def test_extract_toc_from_pdf_bookmark(monkeypatch):
    """PDF có bookmark (get_toc) → trích TOC chương/bài trực tiếp."""
    import fitz

    from src.services.curriculum_ingest import extract_toc_from_pdf

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sách giáo khoa")
    doc.set_toc(
        [
            [1, "Chương I. Số tự nhiên", 1],
            [2, "Bài 1. Tập hợp", 1],
            [2, "Bài 2. Tập hợp số tự nhiên", 1],
            [1, "Chương II. Số nguyên", 1],
        ]
    )
    content = doc.tobytes()
    doc.close()

    entries, source = extract_toc_from_pdf(content)
    assert source == "pdf-bookmark"
    chapters = [e for e in entries if e[0] == 1]
    lessons = [e for e in entries if e[0] == 2]
    assert [c[1] for c in chapters] == ["Chương I. Số tự nhiên", "Chương II. Số nguyên"]
    assert len(lessons) == 2


def test_extract_toc_from_pdf_vlm_failure_degrades(monkeypatch):
    """VLM đọc TOC thất bại → trả ([] , "pdf") thay vì nâng exception (không 500)."""
    import fitz

    from src.services import vlm as vlm_mod
    from src.services.curriculum_ingest import extract_toc_from_pdf

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "SGK")
    content = doc.tobytes()
    doc.close()

    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(
        vlm_mod, "read_pdf_toc", lambda *a, **k: (_ for _ in ()).throw(vlm_mod.VlmUnavailableError("503"))
    )

    entries, source = extract_toc_from_pdf(content)
    assert entries == []
    assert source == "pdf"


def test_save_catalog_from_preview_upserts_without_extract(monkeypatch):
    """Lưu cây đã xem trước → upsert thẳng, không trích lại file/VLM."""
    from src.services import curriculum_ingest

    monkeypatch.setattr(
        curriculum_ingest, "resolve_subject_ids", lambda db, code, grades: {6: 42}
    )
    chapters = [
        {
            "code": "TOAN6_C1",
            "name": "Chương I. Số tự nhiên",
            "semester_number": 1,
            "lessons": [{"code": "TOAN6_C1_B1", "name": "Bài 1. Tập hợp"}],
        },
        {"code": "TOAN6_C2", "name": "Chương II. Số nguyên", "semester_number": 1, "lessons": []},
    ]
    db = _FakeDb()
    result = save_catalog_from_preview(db, chapters, "toan", 6)
    assert result["dry_run"] is False
    assert result["source"] == "preview"
    assert result["inserted"] == 3
    assert len(db.seen) == 3
    assert db.seen[1]["parent_id"] == db.seen[0]["id"]


def test_save_catalog_from_preview_empty_raises(monkeypatch):
    from src.services import curriculum_ingest

    monkeypatch.setattr(
        curriculum_ingest, "resolve_subject_ids", lambda db, code, grades: {6: 42}
    )
    with pytest.raises(ValueError):
        save_catalog_from_preview(_FakeDb(), [], "toan", 6)


def test_pdf_docx_module_paths_are_importable():
    """fitz + docx có trong môi trường (deps) — module không import lỗi."""
    import docx  # noqa: F401
    import fitz  # noqa: F401
