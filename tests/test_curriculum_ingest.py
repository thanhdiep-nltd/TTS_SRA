"""Test offline cho src/services/curriculum_ingest.py — nạp sách tự tách TOC.

PDF = 2 lượt quét bằng VLM (mock read_book_pages: lượt A tìm MỤC LỤC, lượt B phân loại nội dung
CÓ NEO theo ID) + làm giàu từng bài (mock read_lesson_pages). Không gọi API thật.
TXT/DOCX = parse cấu trúc như cũ.
"""

import pytest

from src.services.curriculum_ingest import (
    _align_unit_page_ranges,
    _anchor_id,
    _as_page_int,
    _build_anchor_list,
    _build_tree_from_labels,
    _clean_keywords,
    _clean_sections,
    _enrich_chapters,
    _entries_to_chapters,
    _get_runtime_settings,
    _is_phu_title,
    _is_placeholder,
    _merge_toc_chapters,
    _normalize_title,
    _parse_scan_batch,
    _ranges_from_anchors,
    _sample_indices,
    _sanity_check,
    build_unit_specs_from_chapters,
    detect_semester_from_filename,
    extract_book_structure,
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
                "summary": obj.summary,
                "keywords": obj.keywords,
                "sections": obj.sections,
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


def _make_pdf(pages: int = 4) -> bytes:
    """PDF mini N trang để test luồng sweep (không cần nội dung thật)."""
    import fitz

    doc = fitz.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 72), "SGK")
    content = doc.tobytes()
    doc.close()
    return content


def _fake_read_book_pages(raw_a: list[str], raw_b: list[str]):
    """Fake read_book_pages: lượt A (max_pages) trả raw_a; lượt B (có start_page/prompt) trả raw_b."""

    def fake(path, **kw):
        if kw.get("max_pages") is not None:
            return raw_a
        return raw_b

    return fake


# ============================================================
# Tiện ích / chuẩn hóa
# ============================================================


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


def test_as_page_int():
    assert _as_page_int(5) == 5
    assert _as_page_int("12") == 12
    assert _as_page_int(None) is None
    assert _as_page_int("abc") is None
    assert _as_page_int(True) is None


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


# ============================================================
# Quét 2 lượt: parse lô, merge TOC, neo, khoảng trang
# ============================================================


def test_merge_toc_chapters_groups_multi_page_and_keeps_page():
    parsed = [
        {"toc_page": False},
        {
            "toc_page": True,
            "chapters": [
                {"name": "Số tự nhiên", "page": 3, "lessons": [{"name": "Tập hợp", "page": 3, "kind": "lesson"}]},
            ],
        },
        {
            "toc_page": True,
            "chapters": [
                {"name": "Số tự nhiên", "page": 4, "lessons": [{"name": "Lũy thừa", "page": 6, "kind": "lesson"}]},
                {"name": "Số nguyên", "page": 12, "lessons": [{"name": "Ôn tập chương II", "page": 15, "kind": "phu"}]},
            ],
        },
    ]
    chapters = _merge_toc_chapters(parsed)
    assert len(chapters) == 2
    assert chapters[0]["name"] == "Số tự nhiên"
    assert chapters[0]["page"] == 3  # giữ trang chương đầu tiên (metadata)
    assert [item["name"] for item in chapters[0]["lessons"]] == ["Tập hợp", "Lũy thừa"]
    assert [item["page"] for item in chapters[0]["lessons"]] == [3, 6]
    assert chapters[1]["lessons"][0]["is_phu"] is True


def test_parse_scan_batch_ok_and_self_adjusts_count():
    raw = (
        '{"pages": [{"kind": "frontmatter", "printed_page": 1}, '
        '{"kind": "content", "chapter": "Số tự nhiên", "lesson": "1", "printed_page": 3}]}'
    )
    pages = _parse_scan_batch(raw, 2)
    assert pages is not None and len(pages) == 2
    assert pages[1]["kind"] == "content"
    # AI trả thiếu phần tử → tự chèn {} vừa khít lô (không vứt cả lô); thừa → cắt bớt.
    padded = _parse_scan_batch(raw, 3)
    assert padded is not None and len(padded) == 3
    assert padded[2] == {}
    truncated = _parse_scan_batch(raw, 1)
    assert truncated is not None and len(truncated) == 1
    assert truncated[0]["kind"] == "frontmatter"
    assert _parse_scan_batch(None, 2) is None
    assert _parse_scan_batch('{"pages": "x"}', 2) is None
    assert _parse_scan_batch("không phải json", 2) is None
    assert _parse_scan_batch('{"pages": []}', 2) is None


def test_anchor_id():
    assert _anchor_id(3) == 3
    assert _anchor_id("3") == 3
    assert _anchor_id("3. [Chương I] Bài 1: Tập hợp") == 3
    assert _anchor_id("Tập hợp") is None
    assert _anchor_id(None) is None
    assert _anchor_id(True) is None


def test_build_anchor_list_with_chapter_prefix():
    chapters = [
        {"name": "Chương I", "lessons": [{"name": "Bài 1: Tập hợp"}, {"name": "Bài 2: Lũy thừa"}]},
        {"name": "Chương II", "lessons": [{"name": "Bài 1: Số nguyên âm"}]},
    ]
    anchors = _build_anchor_list(chapters)
    assert anchors.splitlines() == [
        "1. [Chương I] Bài 1: Tập hợp",
        "2. [Chương I] Bài 2: Lũy thừa",
        "3. [Chương II] Bài 1: Số nguyên âm",
    ]


def test_ranges_from_anchors_by_id_and_name_fallback():
    chapters = [
        {"name": "Số tự nhiên", "lessons": [{"name": "Tập hợp"}, {"name": "Lũy thừa"}]},
    ]
    # Trang 0-1 = bài 1 (ID 1), trang 2-3 = bài 2 (ID 2); 1 trang trả tên thay vì ID → fallback tên.
    page_items = [
        {"kind": "content", "lesson": "1"},
        {"kind": "content", "lesson": "1"},
        {"kind": "content", "lesson": "2"},
        {"kind": "content", "lesson": "Lũy thừa"},
        {"kind": "frontmatter"},
    ]
    ranges = _ranges_from_anchors(page_items, chapters)
    assert ranges == {(0, 0): (0, 2), (0, 1): (2, 4)}


def test_ranges_from_anchors_ignores_unknown_id():
    chapters = [{"name": "C1", "lessons": [{"name": "B1"}]}]
    page_items = [
        {"kind": "content", "lesson": "1"},
        {"kind": "content", "lesson": "999"},  # ID không có trong danh sách → bỏ qua, không bịa bài mới
        {"kind": "content", "lesson": "1"},
    ]
    ranges = _ranges_from_anchors(page_items, chapters)
    assert ranges == {(0, 0): (0, 3)}


def test_ranges_from_anchors_empty_returns_none():
    chapters = [{"name": "C1", "lessons": [{"name": "B1"}]}]
    assert _ranges_from_anchors([{"kind": "frontmatter"}], chapters) is None
    assert _ranges_from_anchors([], chapters) is None


def test_extract_book_structure_two_pass_locates_toc(monkeypatch):
    """Cascaded pipeline tìm MỤC LỤC → bóc tách cây Chương/Bài và ánh xạ dải trang PDF."""
    from src.services import vlm as vlm_mod
    from src.services import layout_detector as ld_mod

def test_extract_book_structure_two_pass_locates_toc(monkeypatch):
    """Cascaded pipeline tìm MỤC LỤC → bóc tách cây Chương/Bài và ánh xạ dải trang PDF."""
    from src.services import vlm as vlm_mod
    from src.services import layout_detector as ld_mod

    raw_toc = (
        '{"chapters": ['
        '{"name": "Số tự nhiên", "page": 2, "lessons": ['
        '{"name": "Tập hợp", "page": 3, "kind": "chinh"}'
        ']}'
        ']}'
    )
    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(ld_mod, "find_toc_pages", lambda *a, **k: [1])
    monkeypatch.setattr(ld_mod, "build_page_number_map", lambda *a, **k: {2: 1, 3: 2, 4: 3})
    monkeypatch.setattr(vlm_mod, "read_toc_pages", lambda *a, **k: raw_toc)

    chapters, page_map, warnings, pdf_path = extract_book_structure(_make_pdf(4))
    try:
        assert [c["name"] for c in chapters] == ["Số tự nhiên"]
        assert chapters[0]["lessons"][0]["name"] == "Tập hợp"
        assert chapters[0]["lessons"][0]["start_page"] == 2
        assert chapters[0]["lessons"][0]["end_page"] == 3
        assert not warnings
    finally:
        pdf_path.unlink(missing_ok=True)


def test_extract_book_structure_multi_page_toc(monkeypatch):
    """Kiểm tra TOC trải dài 2 trang được gửi vào VLM cùng lúc trong 1 request."""
    from src.services import vlm as vlm_mod
    from src.services import layout_detector as ld_mod

    raw_toc = (
        '{"chapters": ['
        '{"name": "Chương 1", "page": 2, "lessons": [{"name": "Bài 1", "page": 2, "kind": "chinh"}]},'
        '{"name": "Chương 2", "page": 4, "lessons": [{"name": "Bài 2", "page": 4, "kind": "chinh"}]}'
        ']}'
    )
    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(ld_mod, "find_toc_pages", lambda *a, **k: [0, 1])
    monkeypatch.setattr(ld_mod, "build_page_number_map", lambda *a, **k: {2: 1, 4: 3})
    monkeypatch.setattr(vlm_mod, "read_toc_pages", lambda *a, **k: raw_toc)

    chapters, page_map, warnings, pdf_path = extract_book_structure(_make_pdf(5))
    try:
        assert [c["name"] for c in chapters] == ["Chương 1", "Chương 2"]
        assert len(chapters[0]["lessons"]) == 1
        assert len(chapters[1]["lessons"]) == 1
        assert not warnings
    finally:
        pdf_path.unlink(missing_ok=True)


def test_extract_book_structure_no_toc_fallback_full_scan(monkeypatch):
    from src.services import vlm as vlm_mod
    from src.services import layout_detector as ld_mod

    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(ld_mod, "find_toc_pages", lambda *a, **k: [])
    monkeypatch.setattr(ld_mod, "build_page_number_map", lambda *a, **k: {1: 0, 2: 1, 3: 2})

    chapters, page_map, warnings, pdf_path = extract_book_structure(_make_pdf(3))
    try:
        assert chapters == []
        assert any("Không tìm thấy trang Mục Lục" in w for w in warnings)
    finally:
        pdf_path.unlink(missing_ok=True)


def test_extract_book_structure_requires_vlm(monkeypatch):
    from src.services import vlm as vlm_mod

    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: False)
    with pytest.raises(ValueError):
        extract_book_structure(_make_pdf(2))


def test_extract_book_structure_vlm_failure_raises_value_error(monkeypatch):
    from src.services import vlm as vlm_mod
    from src.services import layout_detector as ld_mod

    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(ld_mod, "find_toc_pages", lambda *a, **k: [1])
    monkeypatch.setattr(
        vlm_mod,
        "read_toc_pages",
        lambda *a, **k: (_ for _ in ()).throw(vlm_mod.VlmUnavailableError("503")),
    )
    with pytest.raises(ValueError):
        extract_book_structure(_make_pdf(2))



def test_build_tree_from_labels_no_toc():
    page_items = [
        {"kind": "content", "chapter": "Số tự nhiên", "lesson": "Tập hợp"},
        {"kind": "content", "chapter": "Số tự nhiên", "lesson": "Tập hợp"},
        {"kind": "content", "chapter": "Số tự nhiên", "lesson": "Lũy thừa"},
        {"kind": "content", "chapter": "Số nguyên", "lesson": "Số nguyên âm"},
    ]
    chapters = _build_tree_from_labels(page_items)
    assert [c["name"] for c in chapters] == ["Số tự nhiên", "Số nguyên"]
    assert [ls["name"] for ls in chapters[0]["lessons"]] == ["Tập hợp", "Lũy thừa"]


# ============================================================
# Làm giàu nội dung (enrichment) — neo ID + context tên bài
# ============================================================


def test_clean_keywords_and_sections():
    assert _clean_keywords([" Phân số ", "Tập hợp,", "phân số", 5, " "]) == ["Phân số", "Tập hợp"]
    # sections: danh sách {name} theo thứ tự, dedup, bỏ tên rỗng — không kind taxonomy.
    assert _clean_sections(
        [
            {"name": "1. Ghi số tự nhiên"},
            {"name": "Thực hành 1"},
            {"name": "1. Ghi số tự nhiên"},
            {"name": ""},
            "không phải dict",
        ]
    ) == [{"name": "1. Ghi số tự nhiên"}, {"name": "Thực hành 1"}]
    assert _clean_sections("x") == []
    assert _clean_sections(None) == []
    assert _clean_keywords(None) == []


def test_enrich_chapters_uses_anchors_and_context(monkeypatch):
    from src.services import vlm as vlm_mod

    chapters = [
        {
            "name": "Số tự nhiên",
            "lessons": [
                {"name": "Tập hợp", "start_page": 0, "end_page": 1},
                {"name": "Lũy thừa", "start_page": 2, "end_page": 3},
            ],
        }
    ]
    seen_context: list[tuple[str | None, str | None]] = []

    def fake_lesson(path, indices, lesson_name=None, chapter_name=None, **k):
        seen_context.append((lesson_name, chapter_name))
        return (
            '{"summary": "Tóm tắt Tập hợp", "keywords": ["tập hợp", "phần tử"], '
            '"sections": [{"name": "1. Ghi số tự nhiên"}, {"name": "Thực hành 1"}]}'
            if lesson_name == "Tập hợp"
            else '{"summary": "Tóm tắt Lũy thừa", "keywords": ["lũy thừa"], "sections": []}'
        )

    monkeypatch.setattr(vlm_mod, "read_lesson_pages", fake_lesson)
    warnings = _enrich_chapters(chapters, {}, "fake.pdf")
    assert warnings == []
    assert chapters[0]["lessons"][0]["summary"] == "Tóm tắt Tập hợp"
    assert chapters[0]["lessons"][0]["keywords"] == ["tập hợp", "phần tử"]
    assert chapters[0]["lessons"][0]["sections"] == [{"name": "1. Ghi số tự nhiên"}, {"name": "Thực hành 1"}]
    assert chapters[0]["lessons"][1]["summary"] == "Tóm tắt Lũy thừa"
    # context tên bài/chương được truyền cho VLM (neo ngữ cảnh)
    assert ("Tập hợp", "Số tự nhiên") in seen_context
    assert ("Lũy thừa", "Số tự nhiên") in seen_context
    # tổng hợp cấp chương
    assert "Tóm tắt Tập hợp" in chapters[0]["summary"]
    assert chapters[0]["keywords"] == ["tập hợp", "phần tử", "lũy thừa"]


def test_enrich_chapters_skips_failed_lesson(monkeypatch):
    from src.services import vlm as vlm_mod

    chapters = [
        {
            "name": "C1",
            "lessons": [
                {"name": "B1", "start_page": 0, "end_page": 1},
                {"name": "B2", "start_page": 2, "end_page": 3},
            ],
        }
    ]

    def fake_lesson(path, indices, lesson_name=None, **k):
        if lesson_name == "B1":
            return '{"summary": "OK", "keywords": ["k1"], "sections": []}'
        raise vlm_mod.VlmUnavailableError("503")

    monkeypatch.setattr(vlm_mod, "read_lesson_pages", fake_lesson)
    warnings = _enrich_chapters(chapters, {}, "fake.pdf")
    assert any("B2" in w for w in warnings)
    assert chapters[0]["lessons"][0]["summary"] == "OK"
    assert chapters[0]["lessons"][1].get("summary") is None


def test_enrich_chapters_truncated_pdf_only_in_file_lessons(monkeypatch):
    """File cắt ngắn: bài không có dải trang hợp lệ → bỏ làm giàu kèm warning."""
    from src.services import vlm as vlm_mod

    chapters = [
        {
            "name": "Chương I",
            "lessons": [
                {"name": "Tập hợp", "start_page": 0, "end_page": 1},
                {"name": "Lũy thừa", "start_page": 2, "end_page": 3},
                {"name": "Bài 3 (ngoài file)", "start_page": None, "end_page": None},
            ],
        }
    ]
    monkeypatch.setattr(
        vlm_mod,
        "read_lesson_pages",
        lambda path, indices, lesson_name=None, **k: f'{{"summary": "Tóm tắt {lesson_name}", "keywords": [], "sections": []}}',
    )
    warnings = _enrich_chapters(chapters, {}, "fake.pdf")
    assert any("Bài 3 (ngoài file)" in w for w in warnings)
    assert chapters[0]["lessons"][0]["summary"] == "Tóm tắt Tập hợp"
    assert chapters[0]["lessons"][1]["summary"] == "Tóm tắt Lũy thừa"
    assert chapters[0]["lessons"][2].get("summary") is None


def test_enrich_chapters_no_anchor_matches_warns():
    chapters = [{"name": "C1", "lessons": [{"name": "B1", "start_page": None, "end_page": None}]}]
    warnings = _enrich_chapters(chapters, {}, "fake.pdf")
    assert any("không có trang nội dung" in w for w in warnings)


def test_align_unit_page_ranges_truncated_pdf_sets_none():
    """PDF chỉ có 20 trang nhưng TOC có bài ở trang 93 -> start_page và end_page phải là None (không bị clamp)."""
    chapters = [
        {
            "name": "Chương 1",
            "lessons": [
                {"name": "Bài 1", "page": 7},
                {"name": "Bài 2", "page": 10},
            ],
        },
        {
            "name": "Chương 3",
            "lessons": [
                {"name": "Bài tập cuối chương 3", "page": 93},
            ],
        },
    ]
    page_map = {7: 6, 10: 9}
    _align_unit_page_ranges(chapters, page_map, total_pages=20)
    # Bài 1 & 2 trong 20 trang
    assert chapters[0]["lessons"][0]["start_page"] == 6
    assert chapters[0]["lessons"][0]["end_page"] == 8
    assert chapters[0]["lessons"][1]["start_page"] == 9
    assert chapters[0]["lessons"][1]["end_page"] == 19
    # Bài tập cuối chương 3 ngoài 20 trang -> start_page & end_page là None
    assert chapters[1]["lessons"][0]["start_page"] is None
    assert chapters[1]["lessons"][0]["end_page"] is None


def test_align_unit_page_ranges_dynamic_offset_scan_pdf():
    """Khi PDF scan ảnh (page_map rỗng), tính Dynamic Offset từ vị trí toc_pages."""
    chapters = [
        {
            "name": "Chương 1",
            "page": 6,
            "lessons": [
                {"name": "Bài 1", "page": 6},
                {"name": "Bài 4", "page": 16},
                {"name": "Bài 5", "page": 20},
            ],
        },
    ]
    # toc_pages ở PDF index [4, 5], first_printed = 6 -> offset = (5+1) - 6 = 0
    _align_unit_page_ranges(chapters, {}, total_pages=127, toc_pages=[4, 5])
    assert chapters[0]["lessons"][0]["start_page"] == 6
    assert chapters[0]["lessons"][0]["end_page"] == 15
    assert chapters[0]["lessons"][1]["start_page"] == 16
    assert chapters[0]["lessons"][1]["end_page"] == 19
    assert chapters[0]["lessons"][2]["start_page"] == 20
    assert chapters[0]["lessons"][2]["end_page"] == 126


def test_align_unit_page_ranges_dynamic_offset_safety_bounds_and_empty():
    """Kiểm tra an toàn: offset bất thường ngoài [-5..10] hoặc toc_pages rỗng -> fallback về 0 an toàn."""
    chapters = [
        {
            "name": "Chương 1",
            "page": 10,
            "lessons": [{"name": "Bài 1", "page": 10}],
        }
    ]
    # toc_pages rỗng -> không crash, offset = 0 -> start_page = 10
    _align_unit_page_ranges(chapters, {}, total_pages=50, toc_pages=[])
    assert chapters[0]["lessons"][0]["start_page"] == 10

    # offset dị thường (toc_pages=[40], first_printed=10 -> raw_offset=31 > 10) -> fallback offset = 0
    _align_unit_page_ranges(chapters, {}, total_pages=50, toc_pages=[40])
    assert chapters[0]["lessons"][0]["start_page"] == 10



# ============================================================
# Specs / upsert / preview / ingest_book
# ============================================================


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


def test_build_unit_specs_from_chapters_with_lessons_and_enrich():
    chapters = [
        {
            "name": "Số tự nhiên",
            "summary": "Tóm tắt chương",
            "keywords": ["số tự nhiên"],
            "lessons": [{"name": "Tập hợp", "summary": "Tóm tắt bài", "keywords": ["tập hợp"], "sections": [{"name": "1. Ghi số tự nhiên"}]}],
        }
    ]
    specs = build_unit_specs_from_chapters(chapters, "toan", 6, 1, include_lessons=True)
    assert specs[0]["summary"] == "Tóm tắt chương"
    assert specs[1]["summary"] == "Tóm tắt bài"
    assert specs[1]["keywords"] == ["tập hợp"]
    assert specs[1]["sections"][0]["name"] == "1. Ghi số tự nhiên"


def test_upsert_unit_tree_links_parents_persists_phu_and_enrich():
    chapters = [
        {
            "name": "Số tự nhiên",
            "summary": "Tóm tắt chương",
            "lessons": [
                {"name": "Tập hợp", "summary": "Tóm tắt bài", "keywords": ["tập hợp"], "sections": [{"name": "1. Ghi số tự nhiên"}]},
                {"name": "Ôn tập chương I", "is_phu": True},
            ],
        }
    ]
    specs = build_unit_specs_from_chapters(chapters, "toan", 6, 1, include_lessons=True)
    db = _FakeDb()
    inserted, updated = upsert_unit_tree(db, specs, subject_id=42, grade=6)
    assert inserted == 3
    assert updated == 0
    assert db.committed
    lesson = next(s for s in db.seen if s["code"] == "TOAN6_C1_B1")
    chapter = next(s for s in db.seen if s["code"] == "TOAN6_C1")
    assert lesson["parent_id"] == chapter["id"]
    assert lesson["summary"] == "Tóm tắt bài"
    assert lesson["keywords"] == ["tập hợp"]
    assert lesson["sections"][0]["name"] == "1. Ghi số tự nhiên"
    phu = next(s for s in db.seen if s["name"] == "Ôn tập chương I")
    assert phu["is_phu"] is True


def test_upsert_unit_tree_overwrite_enrichment_flag():
    """Kiểm tra cờ overwrite_enrichment: True xóa sạch summary cũ về None, False giữ lại summary cũ."""
    class _MockUnit:
        def __init__(self, code, name, summary="Old summary", keywords=["old"], sections=[{"name": "old"}]):
            self.id = 1
            self.code = code
            self.name = name
            self.summary = summary
            self.keywords = keywords
            self.sections = sections
            self.semester_number = 1
            self.parent_id = None
            self.is_phu = False
            self.is_active = True
            self.book_id = 1

    class _MockDb:
        def __init__(self, existing_unit):
            self.unit = existing_unit
            self.committed = False

        def execute(self, stmt):
            class _Res:
                def __init__(self, u):
                    self.u = u
                def scalars(self):
                    return self
                def first(self):
                    return self.u
            return _Res(self.unit)

        def add(self, obj):
            pass

        def flush(self):
            pass

        def commit(self):
            self.committed = True

    # 1. Khi overwrite_enrichment=True (mặc định): spec có summary=None -> unit.summary bị xóa về None
    unit1 = _MockUnit("TOAN6_C1_B1", "Bài 1", summary="Old summary")
    db1 = _MockDb(unit1)
    spec1 = [{"code": "TOAN6_C1_B1", "name": "Bài 1", "semester_number": 1, "parent_code": None, "summary": None, "keywords": None, "sections": None}]
    upsert_unit_tree(db1, spec1, subject_id=42, grade=6, overwrite_enrichment=True)
    assert unit1.summary is None
    assert unit1.keywords is None
    assert unit1.sections is None

    # 2. Khi overwrite_enrichment=False: spec có summary=None -> unit.summary cũ được GIỮ LẠI
    unit2 = _MockUnit("TOAN6_C1_B1", "Bài 1", summary="Old summary")
    db2 = _MockDb(unit2)
    spec2 = [{"code": "TOAN6_C1_B1", "name": "Bài 1", "semester_number": 1, "parent_code": None, "summary": None, "keywords": None, "sections": None}]
    upsert_unit_tree(db2, spec2, subject_id=42, grade=6, overwrite_enrichment=False)
    assert unit2.summary == "Old summary"


def test_ingest_book_dry_run_no_db_write():
    db = _FakeDb()
    result = ingest_book(db, "toan6_tap1.txt", _MD_TOC.encode(), "toan", 6, dry_run=True)
    assert result["dry_run"] is True
    assert result["source"] == "text"
    assert result["semester"] == 1  # từ tên file
    assert len(result["chapters"]) == 2
    assert result["inserted"] == 0
    assert db.committed is False


def test_ingest_book_pdf_dry_run_with_enrich(monkeypatch):
    """PDF: mock 2 lượt quét (TOC + neo) + làm giàu → preview chứa summary/keywords/sections."""
    from src.services import vlm as vlm_mod
    from src.services import layout_detector as ld_mod

    raw_toc = (
        '{"chapters": ['
        '{"name": "Số tự nhiên", "page": 1, "lessons": ['
        '{"name": "Tập hợp", "page": 2, "kind": "chinh"}'
        ']}'
        ']}'
    )
    enrich_raw = (
        '{"summary": "Tóm tắt bài Tập hợp", "keywords": ["tập hợp", "phần tử"], '
        '"sections": [{"name": "1. Ghi số tự nhiên"}]}'
    )

    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(ld_mod, "find_toc_pages", lambda *a, **k: [0])
    monkeypatch.setattr(ld_mod, "build_page_number_map", lambda *a, **k: {1: 0, 2: 1, 3: 2, 4: 3})
    monkeypatch.setattr(vlm_mod, "read_toc_pages", lambda *a, **k: raw_toc)
    monkeypatch.setattr(vlm_mod, "read_lesson_pages", lambda *a, **k: enrich_raw)

    db = _FakeDb()
    result = ingest_book(db, "toan6_tap1.pdf", _make_pdf(4), "toan", 6, include_lessons=True, dry_run=True)
    assert result["dry_run"] is True
    assert result["source"] == "pdf-vlm"
    assert len(result["chapters"]) == 1
    lesson = result["chapters"][0]["lessons"][0]
    assert lesson["summary"] == "Tóm tắt bài Tập hợp"
    assert lesson["keywords"] == ["tập hợp", "phần tử"]
    assert lesson["sections"][0]["name"] == "1. Ghi số tự nhiên"
    assert db.committed is False


def test_ingest_book_pdf_enrich_off_still_gets_tree(monkeypatch):
    """enrich=false: vẫn lấy cây TOC nhưng KHÔNG gọi làm giàu."""
    from src.services import vlm as vlm_mod
    from src.services import layout_detector as ld_mod

    raw_toc = (
        '{"chapters": ['
        '{"name": "Số tự nhiên", "page": 1, "lessons": ['
        '{"name": "Tập hợp", "page": 2, "kind": "chinh"}'
        ']}'
        ']}'
    )
    monkeypatch.setattr(vlm_mod, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(ld_mod, "find_toc_pages", lambda *a, **k: [0])
    monkeypatch.setattr(ld_mod, "build_page_number_map", lambda *a, **k: {1: 0, 2: 1, 3: 2})
    monkeypatch.setattr(vlm_mod, "read_toc_pages", lambda *a, **k: raw_toc)
    calls: list = []
    monkeypatch.setattr(vlm_mod, "read_lesson_pages", lambda *a, **k: calls.append(1) or "{}")

    db = _FakeDb()
    result = ingest_book(db, "toan6.pdf", _make_pdf(3), "toan", 6, include_lessons=True, dry_run=True, enrich=False)
    assert result["chapters"][0]["lessons"][0]["summary"] is None
    assert calls == []


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
            "summary": "Tóm tắt chương",
            "lessons": [
                {
                    "code": "TOAN6_C1_B1",
                    "name": "Tập hợp",
                    "is_phu": False,
                    "summary": "Tóm tắt bài",
                    "keywords": ["tập hợp"],
                }
            ],
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
    assert db.seen[1]["summary"] == "Tóm tắt bài"
    assert db.seen[1]["keywords"] == ["tập hợp"]


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


def test_build_page_number_map_linear_interpolation(tmp_path):
    """Kiểm tra bóc tách số trang in và nội suy tuyến tính."""
    from src.services.layout_detector import build_page_number_map
    import fitz

    doc = fitz.open()
    for i in range(5):
        page = doc.new_page()
        if i in (1, 3):
            page.insert_text((50, 750), f"Trang {i + 1}")
    pdf_file = tmp_path / "test_map.pdf"
    doc.save(str(pdf_file))
    doc.close()

    page_map = build_page_number_map(pdf_file)
    assert page_map[2] == 1
    assert page_map[4] == 3
    assert page_map[3] == 2


def test_parse_dynamic_toc_json_handles_latex_and_variants():
    """Kiểm tra parser JSON cây TOC an toàn trước escape LaTeX và các cấu trúc biến thể."""
    from src.services.vlm import parse_dynamic_toc_json

    raw_json = r"""
    {
      "chapters": [
        {
          "name": "CHƯƠNG I: SỐ TỰ NHIÊN",
          "page": 4,
          "lessons": [
            {"name": "Bài 1. Tập hợp $A \subset \mathbb{N}$", "page": 4, "kind": "chinh"},
            {"name": "Bài 11. Hoạt động thực hành và trải nghiệm: Sử dụng máy tính", "page": 35, "kind": "phu"}
          ]
        }
      ]
    }
    """
    chapters = parse_dynamic_toc_json(raw_json)
    assert len(chapters) == 1
    assert chapters[0]["name"] == "CHƯƠNG I: SỐ TỰ NHIÊN"
    assert len(chapters[0]["lessons"]) == 2
    assert "Bài 11" in chapters[0]["lessons"][1]["name"]
    assert chapters[0]["lessons"][1]["kind"] == "phu"


def test_find_toc_pages_with_keyword(tmp_path):
    """Kiểm tra find_toc_pages nhận diện trang chứa từ khóa MỤC LỤC."""
    from src.services.layout_detector import find_toc_pages
    import fitz

    doc = fitz.open()
    doc.new_page()  # Page 0: Bìa
    p1 = doc.new_page()  # Page 1: MỤC LỤC
    p1.insert_text((50, 50), "MỤC LỤC\nChương 1: Số tự nhiên ...... 4\nChương 2: Số nguyên ...... 40")
    doc.new_page()  # Page 2: Nội dung
    pdf_file = tmp_path / "test_toc.pdf"
    doc.save(str(pdf_file))
    doc.close()

    toc_indices = find_toc_pages(pdf_file)
    assert toc_indices == [1]


def test_sample_indices_inclusive_behavior():
    """Kiểm tra _sample_indices: xử lý chính xác dải [start, end] inclusive, không bị rỗng khi start==end."""
    # 1. 1 trang duy nhất (start == end) -> trả về đúng 1 trang [19], không được rỗng
    assert _sample_indices(19, 19, 10) == [19]

    # 2. Nhiều trang (start=16, end=18) -> trả về đủ [16, 17, 18], không được bỏ rơi trang cuối 18
    assert _sample_indices(16, 18, 10) == [16, 17, 18]

    # 3. Lấy mẫu đều khi vượt quá cap -> luôn giữ trang đầu + trang cuối
    sampled = _sample_indices(10, 30, 5)
    assert len(sampled) == 5
    assert sampled[0] == 10
    assert sampled[-1] == 30
    assert sampled == [10, 15, 20, 25, 30]

    # 4. Trường hợp không hợp lệ
    assert _sample_indices(20, 18, 10) == []


def test_get_runtime_settings_routes_properly():
    """Kiểm tra _get_runtime_settings tự động suy luận đúng provider từ model name."""
    # 1. Qwen direct
    s_qwen = _get_runtime_settings(vlm_model="qwen3-vl-flash")
    assert s_qwen.vlm_provider == "qwen"
    assert s_qwen.qwen_vlm_model == "qwen3-vl-flash"

    # 2. Gemini via OpenRouter
    s_gemini = _get_runtime_settings(vlm_model="google/gemini-2.0-flash-001")
    assert s_gemini.vlm_provider == "openrouter"
    assert s_gemini.openrouter_vlm_model == "google/gemini-2.0-flash-001"

    # 3. Mimo via OpenRouter
    s_mimo = _get_runtime_settings(vlm_model="xiaomi/mimo-v2.5")
    assert s_mimo.vlm_provider == "openrouter"
    assert s_mimo.openrouter_vlm_model == "xiaomi/mimo-v2.5"

    # 4. GPT-4o-mini via OpenRouter
    s_gpt = _get_runtime_settings(vlm_model="openai/gpt-4o-mini")
    assert s_gpt.vlm_provider == "openrouter"
    assert s_gpt.openrouter_vlm_model == "openai/gpt-4o-mini"

