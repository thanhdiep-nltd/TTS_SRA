"""Test offline cho src/services/curriculum_ingest.py — nạp sách tự tách TOC (PDF=VLM-thuần)."""

import pytest

from src.services.curriculum_ingest import (
    _entries_to_chapters,
    _is_phu_title,
    _is_placeholder,
    _merge_toc_chapters,
    _normalize_title,
    _sanity_check,
    build_unit_specs_from_chapters,
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
                "is_phu": obj.is_phu,
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


def test_normalize_and_filters():
    assert _normalize_title("Số tự nhiên ..... 5") == "Số tự nhiên"
    assert _normalize_title("  Số nguyên  ") == "Số nguyên"
    assert _is_placeholder("Tên chương") is True
    assert _is_placeholder("Tên bài") is True
    assert _is_placeholder("Số tự nhiên") is False
    assert _is_phu_title("Ôn tập chương II") is True
    assert _is_phu_title("Kiểm tra chương III") is True
    assert _is_phu_title("Hoạt động thực hành và trải nghiệm") is True
    assert _is_phu_title("Tập hợp") is False


def test_extract_toc_from_text():
    entries = extract_toc_from_text(_MD_TOC)
    chapters = [e for e in entries if e[0] == 1]
    lessons = [e for e in entries if e[0] == 2]
    assert len(chapters) == 2
    assert chapters[0][1] == "Số tự nhiên"
    assert chapters[1][1] == "Số nguyên"
    assert len(lessons) == 3
    assert lessons[0][1] == "Tập hợp"


def test_entries_to_chapters_tags_phu_and_drops_placeholder():
    entries = [
        (1, "SỐ TỰ NHIÊN ..... 3", 0),
        (2, "Bài 1: Tập hợp", 1),
        (2, "Ôn tập chương I", 2),
        (2, "Tên bài", 3),
        (1, "Số nguyên", 4),
    ]
    chapters = _entries_to_chapters(entries)
    assert [c["name"] for c in chapters] == ["SỐ TỰ NHIÊN", "Số nguyên"]
    assert [x["name"] for x in chapters[0]["lessons"]] == ["Bài 1: Tập hợp", "Ôn tập chương I"]
    assert [x["is_phu"] for x in chapters[0]["lessons"]] == [False, True]


def test_merge_toc_chapters_groups_multi_page():
    parsed = [
        {"toc_page": False},
        {
            "toc_page": True,
            "chapters": [
                {"name": "Số tự nhiên", "lessons": [{"name": "Tập hợp", "kind": "lesson"}]},
            ],
        },
        {
            "toc_page": True,
            "chapters": [
                {"name": "Số tự nhiên", "lessons": [{"name": "Lũy thừa", "kind": "lesson"}]},
                {"name": "Số nguyên", "lessons": [{"name": "Ôn tập chương II", "kind": "phu"}]},
            ],
        },
    ]
    chapters = _merge_toc_chapters(parsed)
    assert len(chapters) == 2
    assert chapters[0]["name"] == "Số tự nhiên"
    assert [item["name"] for item in chapters[0]["lessons"]] == ["Tập hợp", "Lũy thừa"]
    assert chapters[1]["lessons"][0]["is_phu"] is True


def test_sanity_check_warns_on_high_counts_and_dupes():
    chapters = [
        {"name": "C" + str(i), "is_phu": False, "lessons": [{"name": "B" + str(j), "is_phu": False} for j in range(35)]}
        for i in range(8)
    ]
    warnings = _sanity_check(chapters)
    assert any("nhiều hơn mức thường gặp" in w for w in warnings)
    assert any("nhiều hơn mức bình thường" in w for w in warnings)
    dup = [{"name": "Trùng", "is_phu": False, "lessons": []}, {"name": "Trùng", "is_phu": False, "lessons": []}]
    assert any("trùng tên" in w for w in _sanity_check(dup))


def test_build_unit_specs_from_chapters_chapters_only():
    chapters = _entries_to_chapters(extract_toc_from_text(_MD_TOC))
    specs = build_unit_specs_from_chapters(chapters, "toan", 6, 1, include_lessons=False)
    assert [s["code"] for s in specs] == ["TOAN6_C1", "TOAN6_C2"]
    assert specs[0]["semester_number"] == 1
    assert all(s["parent_code"] is None for s in specs)


def test_build_unit_specs_from_chapters_with_lessons():
    chapters = _entries_to_chapters(extract_toc_from_text(_MD_TOC))
    specs = build_unit_specs_from_chapters(chapters, "toan", 6, 2, include_lessons=True)
    codes = [s["code"] for s in specs]
    assert codes == ["TOAN6_C1", "TOAN6_C1_B1", "TOAN6_C1_B2", "TOAN6_C2", "TOAN6_C2_B1"]
    assert specs[1]["parent_code"] == "TOAN6_C1"
    assert specs[4]["parent_code"] == "TOAN6_C2"


def test_upsert_unit_tree_links_parents_and_persists_phu():
    chapters = _entries_to_chapters(extract_toc_from_text(_MD_TOC))
    chapters[0]["lessons"].append({"name": "Ôn tập chương I", "is_phu": True})
    specs = build_unit_specs_from_chapters(chapters, "toan", 6, 1, include_lessons=True)
    db = _FakeDb()
    inserted, updated = upsert_unit_tree(db, specs, subject_id=42, grade=6)
    assert inserted == 6
    assert updated == 0
    assert db.committed
    lesson = next(s for s in db.seen if s["code"] == "TOAN6_C1_B1")
    chapter = next(s for s in db.seen if s["code"] == "TOAN6_C1")
    assert lesson["parent_id"] == chapter["id"]
    phu = next(s for s in db.seen if s["name"] == "Ôn tập chương I")
    assert phu["is_phu"] is True


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


def test_extract_toc_from_pdf_uses_vlm_json(monkeypatch):
    """PDF → VLM-thuần: mock read_pdf_toc trả JSON từng trang → chapters đúng."""
    import fitz

    from src.services import vlm as vlm_mod
    from src.services.curriculum_ingest import extract_toc_from_pdf

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "SGK")
    content = doc.tobytes()
    doc.close()

    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(
        vlm_mod,
        "read_pdf_toc",
        lambda *a, **k: [
            '{"toc_page": false}',
            '{"toc_page": true, "chapters": [{"name": "Số tự nhiên", "lessons": [{"name": "Tập hợp", "kind": "lesson"}]}, {"name": "Số nguyên", "lessons": [{"name": "Ôn tập chương II", "kind": "phu"}]}]}',
        ],
    )

    chapters, source = extract_toc_from_pdf(content)
    assert source == "pdf-vlm"
    assert [c["name"] for c in chapters] == ["Số tự nhiên", "Số nguyên"]
    assert chapters[1]["lessons"][0]["is_phu"] is True


def test_extract_toc_from_pdf_requires_vlm(monkeypatch):
    import fitz

    from src.services import vlm as vlm_mod
    from src.services.curriculum_ingest import extract_toc_from_pdf

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "SGK")
    content = doc.tobytes()
    doc.close()

    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: False)
    with pytest.raises(ValueError):
        extract_toc_from_pdf(content)


def test_extract_toc_from_pdf_vlm_failure_raises_value_error(monkeypatch):
    """VLM lỗi (503) → ValueError (endpoint trả 422), không phải VlmUnavailableError trần."""
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

    with pytest.raises(ValueError):
        extract_toc_from_pdf(content)


def test_save_catalog_from_preview_upserts_without_extract(monkeypatch):
    """Lưu cây đã xem trước → upsert thẳng, không trích lại file/VLM."""
    from src.services import curriculum_ingest

    monkeypatch.setattr(
        curriculum_ingest, "resolve_subject_ids", lambda db, code, grades: {6: 42}
    )
    chapters = [
        {
            "code": "TOAN6_C1",
            "name": "Số tự nhiên",
            "semester_number": 1,
            "is_phu": False,
            "lessons": [{"code": "TOAN6_C1_B1", "name": "Tập hợp", "is_phu": False}],
        },
        {"code": "TOAN6_C2", "name": "Số nguyên", "semester_number": 1, "is_phu": False, "lessons": []},
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
