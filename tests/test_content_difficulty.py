"""Test offline cho pipeline phân tích nội dung đề thi (M1+M2+M3 — plan_cdi_kg_anchored.md).

Không gọi LLM/VLM thật, không chạm Neon. File tạm cho test OCR/VLM ghi vào temp/ (tránh
tmp_path của pytest bị chặn trong một số sandbox).
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import fitz
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.models.enums import FileType
from src.models.tables import CurriculumUnit
from src.schemas.exam_analysis import NodeRef
from src.services import content_difficulty as cd

_TEMP_DIR = Path(__file__).resolve().parents[1] / "temp"


def _fake_llm_response(content: str):
    return SimpleNamespace(content=content)


def _unit(unit_id, code, name, grade=6, semester=1, parent_id=None, is_active=True):
    return CurriculumUnit(
        id=unit_id,
        subject_id=106,
        grade_number=grade,
        parent_id=parent_id,
        code=code,
        name=name,
        semester_number=semester,
        is_active=is_active,
    )


def _resolved(bloom_level, weight, unit_id=None):
    return cd.ResolvedCompetency(
        topic="T",
        bloom_level=bloom_level,
        weight=weight,
        unit_id=unit_id,
        unit_code="X" if unit_id else None,
        unit_name="X" if unit_id else None,
        matched_catalog=unit_id is not None,
    )


def _analysis_item(unit, weight, off_weight=0.0):
    return cd.ResolvedCompetency(
        topic=unit.name,
        excerpt="Cau hoi mau",
        bloom_level=2,
        weight=weight,
        unit_id=unit.id,
        unit_code=unit.code,
        unit_name=unit.name,
        matched_catalog=True,
        off_curriculum=False,
        off_curriculum_weight=off_weight,
        chapter=unit.name,
        lesson=None,
    )


# ---------- CDI ----------


def test_cdi_from_bloom_mix_matches_design_doc_example():
    mix = [(1, 0.40), (2, 0.30), (3, 0.30)]
    assert cd.cdi_from_bloom_mix(mix) == 0.317


def test_cdi_from_bloom_mix_empty_returns_zero():
    assert cd.cdi_from_bloom_mix([]) == 0.0


def test_cdi_from_bloom_mix_zero_total_weight_falls_back_to_equal_weights():
    mix = [(2, 0.0), (4, 0.0)]
    assert cd.cdi_from_bloom_mix(mix) == 0.5


# ---------- M1: extract_exam_text ----------


def _write_temp_pdf(name: str, with_text: bool) -> Path:
    _TEMP_DIR.mkdir(exist_ok=True)
    path = _TEMP_DIR / name
    doc = fitz.open()
    page = doc.new_page()
    if with_text:
        page.insert_text((72, 72), "De kiem tra Toan - Cau 1: Tinh dao ham.")
    doc.save(path)
    doc.close()
    return path


def test_extract_exam_text_reads_native_text_layer():
    pdf = _write_temp_pdf("_test_exam_native.pdf", with_text=True)
    try:
        assert "Toan" in cd.extract_exam_text(pdf, FileType.PDF)
    finally:
        pdf.unlink(missing_ok=True)


def test_extract_exam_text_uses_vlm_for_short_pdf(monkeypatch):
    pdf = _write_temp_pdf("_test_exam_blank.pdf", with_text=False)
    try:
        monkeypatch.setattr(
            cd,
            "_pdf_extract",
            lambda: SimpleNamespace(extract_text_layer=lambda data, **_kw: "", extract_with_tesseract=lambda *a, **k: ""),
        )
        monkeypatch.setattr(cd.vlm, "is_configured", lambda *a, **k: True)
        monkeypatch.setattr(cd.vlm, "read_pdf_pages", lambda *a, **k: "Cau 1: $x^2-4=0$")
        out = cd.extract_exam_text(pdf, FileType.PDF)
        assert "x^2-4=0" in out
    finally:
        pdf.unlink(missing_ok=True)


def test_extract_exam_text_falls_back_when_vlm_unavailable(monkeypatch):
    pdf = _write_temp_pdf("_test_exam_scanned.pdf", with_text=False)
    try:
        def _boom(*_a, **_k):
            raise RuntimeError("tesseract binary not found")

        monkeypatch.setattr(cd, "_pdf_extract", lambda: SimpleNamespace(extract_text_layer=lambda data, **_kw: "", extract_with_tesseract=_boom))
        monkeypatch.setattr(cd.vlm, "is_configured", lambda *a, **k: False)
        assert cd.extract_exam_text(pdf, FileType.PDF) == ""
    finally:
        pdf.unlink(missing_ok=True)


def test_extract_exam_text_image_prefers_vlm(monkeypatch):
    p = _TEMP_DIR / "_test_exam.png"
    _TEMP_DIR.mkdir(exist_ok=True)
    p.write_bytes(b"\x89PNG fake")
    try:
        monkeypatch.setattr(cd.vlm, "read_image_bytes", lambda *a, **k: "Cau 2: $\\lim$")
        assert "\\lim" in cd.extract_exam_text(p, FileType.IMAGE)
    finally:
        p.unlink(missing_ok=True)


# ---------- M2: shortlist + mapper ----------


@pytest.fixture
def unit_db():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE curriculum_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id INTEGER NOT NULL,
                    grade_number INTEGER NOT NULL,
                    parent_id INTEGER,
                    code VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    semester_number INTEGER,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_phu BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO curriculum_units (subject_id, grade_number, code, name, semester_number) "
                "VALUES (106, 6, 'TOAN6_C1', 'So tu nhien', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO curriculum_units (subject_id, grade_number, code, name, semester_number) "
                "VALUES (106, 6, 'TOAN6_C4', 'Thong ke', 2)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO curriculum_units (subject_id, grade_number, code, name, semester_number) "
                "VALUES (106, 7, 'TOAN7_C1', 'So huu ti', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO curriculum_units (subject_id, grade_number, code, name, semester_number) "
                "VALUES (106, 6, 'TOAN6_HIDDEN', 'An', 1)"
            )
        )
        conn.execute(text("UPDATE curriculum_units SET is_active = 0 WHERE code = 'TOAN6_HIDDEN'"))
        conn.execute(
            text(
                "INSERT INTO curriculum_units (subject_id, grade_number, code, name, semester_number, is_phu) "
                "VALUES (106, 6, 'TOAN6_PHU', 'On tap chuong II', 1, 1)"
            )
        )
    with Session(engine) as session:
        yield session


def test_build_shortlist_filters_grade_semester_and_active(unit_db):
    units = cd.build_shortlist(unit_db, subject_id=106, grade_number=6, semester_number=1)
    assert {u.code for u in units} == {"TOAN6_C1"}


def test_build_shortlist_ignores_filters_when_none(unit_db):
    units = cd.build_shortlist(unit_db, subject_id=106, grade_number=None, semester_number=None)
    assert {u.code for u in units} == {"TOAN6_C1", "TOAN6_C4", "TOAN7_C1"}


def test_build_shortlist_excludes_phu_nodes(unit_db):
    units = cd.build_shortlist(unit_db, subject_id=106, grade_number=6, semester_number=1)
    assert "TOAN6_PHU" not in {u.code for u in units}


def test_build_map_prompt_lists_shortlist_nodes():
    units = [_unit(1, "TOAN6_C1", "So tu nhien"), _unit(2, "TOAN6_C2", "So nguyen", semester=None)]
    prompt = cd.build_map_prompt("Cau 1", units)
    assert "1: So tu nhien (khối 6, HK1)" in prompt
    assert "2: So nguyen (khối 6)" in prompt
    assert "off_curriculum_weight" in prompt


def test_parse_mapped_items_drops_hallucinated_node_into_off_weight():
    raw = (
        '[{"topic":"A","nodes":[{"node_id":1,"weight":0.3},{"node_id":999,"weight":0.3}],'
        '"bloom_level":2,"off_curriculum_weight":0.4}]'
    )
    items = cd.parse_mapped_items(raw, {1, 2})
    assert len(items) == 1
    assert [(n.node_id, n.weight) for n in items[0].nodes] == [(1, 0.3)]
    assert items[0].off_curriculum_weight == pytest.approx(0.7)


def test_parse_mapped_items_caps_three_nodes():
    raw = (
        '[{"topic":"A","nodes":[{"node_id":1,"weight":0.25},{"node_id":2,"weight":0.25},'
        '{"node_id":3,"weight":0.25},{"node_id":4,"weight":0.25}],"bloom_level":3,"off_curriculum_weight":0.0}]'
    )
    items = cd.parse_mapped_items(raw, {1, 2, 3, 4})
    assert len(items[0].nodes) == 3
    assert items[0].off_curriculum_weight == pytest.approx(0.25)


def test_parse_mapped_items_normalizes_weights_to_one():
    raw = '[{"topic":"A","nodes":[{"node_id":1,"weight":0.5}],"bloom_level":2,"off_curriculum_weight":0.0}]'
    items = cd.parse_mapped_items(raw, {1})
    assert items[0].nodes[0].weight == pytest.approx(1.0)


def test_parse_mapped_items_returns_empty_on_malformed():
    assert cd.parse_mapped_items("khong phai json", {1}) == []


def test_map_items_retries_on_malformed_json():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _fake_llm_response("khong phai json"),
        _fake_llm_response(
            '[{"topic":"A","nodes":[{"node_id":1,"weight":1.0}],"bloom_level":2,"off_curriculum_weight":0.0}]'
        ),
    ]
    units = [_unit(1, "TOAN6_C1", "So tu nhien")]
    items = cd.map_items("Cau 1: ..." * 10, units, llm=mock_llm)
    assert len(items) == 1
    assert mock_llm.invoke.call_count == 2


def test_map_items_skips_when_text_too_short():
    assert cd.map_items("ngan", [_unit(1, "TOAN6_C1", "So tu nhien")], llm=MagicMock()) == []


def test_rejudge_null_items_remaps_or_keeps():
    units = [_unit(1, "TOAN6_C1", "So tu nhien")]
    items = [
        cd.MappedItem(topic="Cau A", nodes=[cd.NodeWeight(node_id=1, weight=1.0)], bloom_level=2, off_curriculum_weight=0.0),
        cd.MappedItem(topic="Cau B", nodes=[], bloom_level=3, off_curriculum_weight=1.0),
    ]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '[{"topic":"Cau B","nodes":[{"node_id":1,"weight":1.0}],"bloom_level":3,"off_curriculum_weight":0.0}]'
    )
    out = cd.rejudge_null_items(items, units, llm=mock_llm)
    assert out[0].nodes
    assert out[1].nodes


def test_rejudge_null_items_sets_candidates_when_still_null():
    units = [_unit(1, "TOAN6_C1", "So tu nhien"), _unit(2, "TOAN6_C2", "So nguyen")]
    items = [cd.MappedItem(topic="Cau B", nodes=[], bloom_level=3, off_curriculum_weight=1.0)]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '[{"topic":"Cau B","nodes":[],"bloom_level":3,"off_curriculum_weight":1.0}]'
    )
    out = cd.rejudge_null_items(items, units, llm=mock_llm)
    assert out[0].nodes == []
    assert out[0].candidates == [1, 2]


def test_expand_mapped_resolves_chapter_and_lesson():
    chapter = _unit(1, "TOAN9_C5", "Đường tròn", grade=9)
    lesson = _unit(2, "TOAN9_C5_U1", "Tiếp tuyến", grade=9, parent_id=1)
    item = cd.MappedItem(
        topic="Tiep tuyen",
        nodes=[cd.NodeWeight(node_id=2, weight=0.6), cd.NodeWeight(node_id=1, weight=0.4)],
        bloom_level=3,
        off_curriculum_weight=0.0,
    )
    resolved = cd._expand_mapped([item], [chapter, lesson])
    assert len(resolved) == 2
    by_unit = {r.unit_id: r for r in resolved}
    assert by_unit[2].chapter == "Đường tròn"
    assert by_unit[2].lesson == "Tiếp tuyến"
    assert by_unit[1].chapter == "Đường tròn"
    assert by_unit[1].lesson is None
    assert by_unit[2].off_curriculum is False


# ---------- merge + 5 trục ----------


def test_normalize_resolved_scales_weights_to_one():
    items = [
        cd.MappedItem(topic="A", nodes=[cd.NodeWeight(node_id=1, weight=1.0)], bloom_level=2, off_curriculum_weight=0.0),
        cd.MappedItem(topic="B", nodes=[cd.NodeWeight(node_id=2, weight=0.8)], bloom_level=3, off_curriculum_weight=0.2),
    ]
    resolved = [
        cd.ResolvedCompetency(topic="A", bloom_level=2, weight=1.0, unit_id=1, unit_code="A", unit_name="A", matched_catalog=True),
        cd.ResolvedCompetency(topic="B", bloom_level=3, weight=0.8, unit_id=2, unit_code="B", unit_name="B", matched_catalog=True),
    ]
    resolved, items = cd._normalize_resolved(resolved, items)
    total = sum(r.weight for r in resolved) + sum(it.off_curriculum_weight for it in items)
    assert total == pytest.approx(1.0)
    assert resolved[0].weight == pytest.approx(0.5)  # 1.0 / 2.0
    assert items[1].off_curriculum_weight == pytest.approx(0.1)  # 0.2 / 2.0
    assert resolved[0].weight <= 1.0


def test_normalize_resolved_noop_when_already_one():
    items = [cd.MappedItem(topic="A", nodes=[cd.NodeWeight(node_id=1, weight=1.0)], bloom_level=2, off_curriculum_weight=0.0)]
    resolved = [cd.ResolvedCompetency(topic="A", bloom_level=2, weight=1.0, unit_id=1, unit_code="A", unit_name="A", matched_catalog=True)]
    out, _ = cd._normalize_resolved(resolved, items)
    assert out[0].weight == 1.0


def test_merge_by_unit_sums_weight_and_weighted_rounds_bloom():
    merged = cd.merge_by_unit([_resolved(2, 0.3, 1), _resolved(4, 0.1, 1)])
    bloom, weight = merged[1]
    assert bloom == 3
    assert weight == pytest.approx(0.4)


def test_merge_by_unit_zero_total_weight_uses_simple_mean():
    bloom, weight = cd.merge_by_unit([_resolved(2, 0.0, 1), _resolved(4, 0.0, 1)])[1]
    assert bloom == 3
    assert weight == 0.0


def test_merge_by_unit_skips_items_without_unit_id():
    assert cd.merge_by_unit([_resolved(2, 1.0, unit_id=None)]) == {}


def test_build_content_analysis_coverage_and_ratio():
    catalog = [_unit(1, "A", "Tap hop"), _unit(2, "B", "So nguyen"), _unit(3, "C", "Phan so")]
    items = [_analysis_item(catalog[0], 0.25), _analysis_item(catalog[1], 0.5)]
    analysis = cd.build_content_analysis(cd.AnalysisBuildInput(items=items, catalog=catalog, cdi=0.4, model=None))
    assert analysis.coverage.catalog_total == 3
    assert analysis.coverage.matched == 2
    assert analysis.coverage.ratio == pytest.approx(2 / 3)
    assert {u.unit_code: u.weight for u in analysis.coverage_units} == {"A": 0.25, "B": 0.5, "C": 0.0}


def test_build_content_analysis_off_weight_and_node_ref():
    catalog = [_unit(1, "A", "Tap hop"), _unit(2, "B", "So nguyen")]
    items = [
        cd.ResolvedCompetency(
            topic="Cau1", bloom_level=2, weight=0.5, unit_id=1, unit_code="A", unit_name="Tap hop",
            matched_catalog=True, off_curriculum=False, off_curriculum_weight=0.2, chapter="C1", lesson=None,
        ),
        cd.ResolvedCompetency(
            topic="Cau2", bloom_level=3, weight=0.3, unit_id=2, unit_code="B", unit_name="So nguyen",
            matched_catalog=True, off_curriculum=False, off_curriculum_weight=0.1, chapter="C1", lesson=None,
        ),
    ]
    analysis = cd.build_content_analysis(cd.AnalysisBuildInput(items=items, catalog=catalog, cdi=0.4, model=None))
    assert analysis.off_curriculum_weight == pytest.approx(0.3)
    assert analysis.items[0].node_ref == NodeRef(node_id=1, chapter="C1", lesson=None)


def test_build_content_analysis_concentration():
    catalog = [_unit(1, "A", "Tap hop"), _unit(2, "B", "So nguyen")]
    analysis = cd.build_content_analysis(
        cd.AnalysisBuildInput(
            items=[_analysis_item(catalog[0], 0.65), _analysis_item(catalog[1], 0.35)],
            catalog=catalog,
            cdi=0.4,
            model=None,
        )
    )
    assert analysis.concentration.is_concentrated is True
    assert analysis.concentration.top_share == pytest.approx(0.65)
