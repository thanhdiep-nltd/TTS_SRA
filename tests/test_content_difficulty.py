"""Test offline cho pipeline tự động tính CDI (không gọi OpenAI/Tesseract thật, không chạm Neon)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import fitz
import pytest

from src.models.enums import FileType
from src.models.tables import CurriculumUnit, ExamPaper, Subject
from src.schemas.exam_analysis import EvidenceRef
from src.services import content_difficulty
from src.services.retrieval import RetrievalUnavailableError


def test_cdi_from_bloom_mix_matches_design_doc_example():
    # 70% Bloom 1-2, 30% Bloom 3 -> đề dễ-trung bình (xem scripts/seed_exam_validity_demo.py).
    mix = [(1, 0.40), (2, 0.30), (3, 0.30)]
    assert content_difficulty.cdi_from_bloom_mix(mix) == 0.317


def test_cdi_from_bloom_mix_empty_returns_zero():
    assert content_difficulty.cdi_from_bloom_mix([]) == 0.0


def test_cdi_from_bloom_mix_zero_total_weight_falls_back_to_equal_weights():
    # LLM trả toàn weight 0 -> không chia cho 0, coi như trọng số đều nhau.
    mix = [(2, 0.0), (4, 0.0)]
    assert content_difficulty.cdi_from_bloom_mix(mix) == 0.5


def _fake_llm_response(content: str):
    return SimpleNamespace(content=content)


def test_classify_competencies_parses_valid_json(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '```json\n[{"topic": "Đại số", "bloom_level": 2, "weight": 0.6}, '
        '{"topic": "Hình học", "bloom_level": 3, "weight": 0.4}]\n```'
    )
    monkeypatch.setattr(content_difficulty, "get_llm", lambda: mock_llm)

    result = content_difficulty.classify_competencies("Câu 1: ..." * 10)

    assert len(result) == 2
    assert result[0].topic == "Đại số"
    assert result[0].bloom_level == 2
    assert pytest.approx(sum(g.weight for g in result)) == 1.0


def test_classify_competencies_returns_empty_on_malformed_json(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response("không phải JSON đâu nha")
    monkeypatch.setattr(content_difficulty, "get_llm", lambda: mock_llm)

    assert content_difficulty.classify_competencies("Câu 1: ..." * 10) == []


def test_classify_competencies_skips_llm_when_text_too_short(monkeypatch):
    mock_llm = MagicMock()
    monkeypatch.setattr(content_difficulty, "get_llm", lambda: mock_llm)

    assert content_difficulty.classify_competencies("quá ngắn") == []
    mock_llm.invoke.assert_not_called()


def _unit(code: str, name: str) -> CurriculumUnit:
    return CurriculumUnit(code=code, name=name, subject_id=1, grade_number=6)


def _catalog_unit(code: str, name: str, unit_id: int = 1) -> CurriculumUnit:
    unit = _unit(code, name)
    unit.id = unit_id
    return unit


def test_build_classify_prompt_lists_catalog_codes():
    catalog = [_unit("TOAN6-TAPHOP", "Tập hợp các số tự nhiên"), _unit("TOAN6-SONGUYEN", "Số nguyên")]
    prompt = content_difficulty.build_classify_prompt("Câu 1: ...", catalog)

    assert "TOAN6-TAPHOP — Tập hợp các số tự nhiên" in prompt
    assert "TOAN6-SONGUYEN — Số nguyên" in prompt
    assert "unit_code" in prompt


def test_build_classify_prompt_omits_unit_code_when_catalog_empty():
    prompt = content_difficulty.build_classify_prompt("Câu 1: ...", [])

    assert "unit_code" not in prompt
    assert "DANH SÁCH CHỦ ĐỀ" not in prompt


def test_classify_competencies_parses_unit_code_and_excerpt(monkeypatch):
    catalog = [_unit("TOAN6-SONGUYEN", "Số nguyên")]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '[{"topic": "Số nguyên", "bloom_level": 2, "weight": 1.0, "unit_code": "TOAN6-SONGUYEN", '
        '"excerpt": "Câu 3: Tính (-12) + 25."}]'
    )
    monkeypatch.setattr(content_difficulty, "get_llm", lambda: mock_llm)

    result = content_difficulty.classify_competencies("Câu 1: ..." * 10, catalog)

    assert result[0].unit_code == "TOAN6-SONGUYEN"
    assert result[0].excerpt == "Câu 3: Tính (-12) + 25."


def test_classify_competencies_nullifies_hallucinated_unit_code(monkeypatch):
    catalog = [_unit("TOAN6-SONGUYEN", "Số nguyên")]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _fake_llm_response(
        '[{"topic": "Đại số", "bloom_level": 2, "weight": 1.0, "unit_code": "TOAN6-KHONGTONTAI"}]'
    )
    monkeypatch.setattr(content_difficulty, "get_llm", lambda: mock_llm)

    result = content_difficulty.classify_competencies("Câu 1: ..." * 10, catalog)

    assert result[0].unit_code is None


def test_extract_exam_text_reads_native_text_layer(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Đề kiểm tra môn Toán - Câu 1: Tính đạo hàm của hàm số.")
    pdf_path = tmp_path / "exam.pdf"
    doc.save(pdf_path)
    doc.close()

    text = content_difficulty.extract_exam_text(pdf_path, FileType.PDF)

    assert "Toán" in text


def test_extract_exam_text_falls_back_gracefully_when_ocr_unavailable(tmp_path, monkeypatch):
    doc = fitz.open()
    doc.new_page()  # trang trắng -> text-layer rỗng, buộc thử fallback OCR
    pdf_path = tmp_path / "scanned.pdf"
    doc.save(pdf_path)
    doc.close()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("tesseract binary not found")

    monkeypatch.setattr(
        content_difficulty,
        "_pdf_extract",
        lambda: SimpleNamespace(
            extract_text_layer=lambda data, **_kw: "",
            extract_with_tesseract=_boom,
        ),
    )

    text = content_difficulty.extract_exam_text(pdf_path, FileType.PDF)

    assert text == ""


def _resolved(bloom_level, weight, unit_id=None):
    return content_difficulty.ResolvedCompetency(
        topic="Chủ đề",
        excerpt=None,
        bloom_level=bloom_level,
        weight=weight,
        unit_id=unit_id,
        unit_code="X" if unit_id else None,
        unit_name="X" if unit_id else None,
        matched_catalog=unit_id is not None,
    )


def _analysis_item(
    unit: CurriculumUnit,
    weight: float,
    matched_catalog: bool = True,
    evidence: EvidenceRef | None = None,
    off_curriculum: bool | None = None,
):
    return content_difficulty.ResolvedCompetency(
        topic=unit.name,
        excerpt="Cau hoi mau",
        bloom_level=2,
        weight=weight,
        unit_id=unit.id,
        unit_code=unit.code,
        unit_name=unit.name,
        matched_catalog=matched_catalog,
        evidence=evidence,
        off_curriculum=off_curriculum,
    )


def test_resolve_units_uses_catalog_match_without_touching_db():
    fake_db = MagicMock()
    unit = _unit("TOAN6-SONGUYEN", "Số nguyên")
    ctx = content_difficulty.AnalysisContext(
        subject_id=1, subject_code="TOAN", grade_number=6, catalog={"TOAN6-SONGUYEN": unit}
    )
    guess = content_difficulty.CompetencyGuess(
        topic="Số nguyên", bloom_level=2, weight=1.0, unit_code="TOAN6-SONGUYEN"
    )

    resolved = content_difficulty._resolve_units(fake_db, ctx, [guess])

    assert resolved[0].matched_catalog is True
    assert resolved[0].unit_code == "TOAN6-SONGUYEN"
    assert resolved[0].unit_name == "Số nguyên"
    fake_db.execute.assert_not_called()


def test_resolve_units_falls_back_to_topic_when_no_catalog_match():
    fake_db = MagicMock()
    fake_db.execute.return_value.scalar_one_or_none.return_value = None
    ctx = content_difficulty.AnalysisContext(subject_id=1, subject_code="TOAN", grade_number=6, catalog={})
    guess = content_difficulty.CompetencyGuess(topic="Đại số", bloom_level=2, weight=1.0)

    resolved = content_difficulty._resolve_units(fake_db, ctx, [guess])

    assert resolved[0].matched_catalog is False
    assert resolved[0].unit_name == "Đại số"


def test_resolve_units_returns_none_unit_when_grade_unknown():
    fake_db = MagicMock()
    ctx = content_difficulty.AnalysisContext(subject_id=1, subject_code="TOAN", grade_number=None, catalog={})
    guess = content_difficulty.CompetencyGuess(topic="Đại số", bloom_level=2, weight=1.0)

    resolved = content_difficulty._resolve_units(fake_db, ctx, [guess])

    assert resolved[0].unit_id is None
    assert resolved[0].matched_catalog is False
    fake_db.execute.assert_not_called()


def test_merge_by_unit_sums_weight_and_weighted_rounds_bloom():
    unit_id = 1
    items = [_resolved(2, 0.3, unit_id), _resolved(4, 0.1, unit_id)]

    bloom, weight = content_difficulty.merge_by_unit(items)[unit_id]

    assert bloom == 3  # (2*0.3 + 4*0.1)/0.4 = 2.5 -> half-up -> 3
    assert weight == pytest.approx(0.4)


def test_merge_by_unit_zero_total_weight_uses_simple_mean():
    unit_id = 1
    items = [_resolved(2, 0.0, unit_id), _resolved(4, 0.0, unit_id)]

    bloom, weight = content_difficulty.merge_by_unit(items)[unit_id]

    assert bloom == 3  # mean(2, 4) = 3, không chia cho 0
    assert weight == 0.0


def test_merge_by_unit_skips_items_without_unit_id():
    items = [_resolved(2, 1.0, unit_id=None)]

    assert content_difficulty.merge_by_unit(items) == {}


def test_best_evidence_returns_top_hit_fields(monkeypatch):
    hits = [
        {"score": 0.62, "heading": "Chương 2 > Bài 13", "source_md": "toan6.md", "text": "..."},
        {"score": 0.40, "heading": "Khác", "source_md": "toan6_b.md", "text": "..."},
    ]
    monkeypatch.setattr(content_difficulty.retrieval, "search_textbook", lambda *a, **k: hits)

    evidence = content_difficulty._best_evidence("Số nguyên", mon="toan", lop="6")

    assert evidence.score == 0.62
    assert evidence.heading == "Chương 2 > Bài 13"
    assert evidence.source_md == "toan6.md"


def test_best_evidence_returns_none_when_no_hits(monkeypatch):
    monkeypatch.setattr(content_difficulty.retrieval, "search_textbook", lambda *a, **k: [])

    assert content_difficulty._best_evidence("Số nguyên", mon="toan", lop="6") is None


def test_collect_evidence_fail_soft_when_retrieval_unavailable(monkeypatch):
    def _boom(*_a, **_k):
        raise RetrievalUnavailableError("Qdrant down")

    monkeypatch.setattr(content_difficulty.retrieval, "search_textbook", _boom)
    guesses = [content_difficulty.CompetencyGuess(topic="Số nguyên", bloom_level=2, weight=1.0)]

    evidences, rag_available = content_difficulty._collect_evidence(guesses, mon="toan", lop="6")

    assert evidences == [None]
    assert rag_available is False


def test_collect_evidence_builds_query_from_topic_and_excerpt(monkeypatch):
    captured_queries = []

    def _fake_search(query, mon, lop):
        captured_queries.append(query)
        return []

    monkeypatch.setattr(content_difficulty.retrieval, "search_textbook", _fake_search)
    guesses = [
        content_difficulty.CompetencyGuess(topic="Số nguyên", bloom_level=2, weight=1.0, excerpt="Câu 3: (-12)+25."),
        content_difficulty.CompetencyGuess(topic="Tập hợp", bloom_level=1, weight=1.0),
    ]

    evidences, rag_available = content_difficulty._collect_evidence(guesses, mon="toan", lop="6")

    assert captured_queries == ["Số nguyên. Câu 3: (-12)+25.", "Tập hợp"]
    assert evidences == [None, None]
    assert rag_available is True


def test_attach_evidence_marks_on_curriculum_false_when_evidence_found():
    item = _resolved(2, 1.0, unit_id=1)
    evidence = EvidenceRef(score=0.7, heading="Bài 1", source_md="toan6.md")

    attached = content_difficulty._attach_evidence([item], [evidence], rag_available=True)

    assert attached[0].evidence == evidence
    assert attached[0].off_curriculum is False


def test_attach_evidence_marks_off_curriculum_true_when_no_evidence_found():
    item = _resolved(2, 1.0, unit_id=1)

    attached = content_difficulty._attach_evidence([item], [None], rag_available=True)

    assert attached[0].off_curriculum is True


def test_attach_evidence_marks_none_when_rag_unavailable():
    item = _resolved(2, 1.0, unit_id=1)

    attached = content_difficulty._attach_evidence([item], [None], rag_available=False)

    assert attached[0].off_curriculum is None


def test_build_content_analysis_coverage_and_ratio():
    catalog = [
        _catalog_unit("TOAN6-A", "Tap hop", 1),
        _catalog_unit("TOAN6-B", "So nguyen", 2),
        _catalog_unit("TOAN6-C", "Phan so", 3),
    ]
    items = [_analysis_item(catalog[0], 0.25), _analysis_item(catalog[1], 0.5)]

    analysis = content_difficulty.build_content_analysis(
        content_difficulty.AnalysisBuildInput(items=items, catalog=catalog, rag_available=True, cdi=0.4, model=None)
    )

    assert analysis.coverage.catalog_total == 3
    assert analysis.coverage.matched == 2
    assert analysis.coverage.ratio == pytest.approx(2 / 3)
    assert {unit.unit_code: unit.weight for unit in analysis.coverage_units} == {
        "TOAN6-A": 0.25,
        "TOAN6-B": 0.5,
        "TOAN6-C": 0.0,
    }


def test_build_content_analysis_flags_concentration_above_threshold():
    unit_a = _catalog_unit("TOAN6-A", "Tap hop", 1)
    unit_b = _catalog_unit("TOAN6-B", "So nguyen", 2)

    concentrated = content_difficulty.build_content_analysis(
        content_difficulty.AnalysisBuildInput(
            items=[_analysis_item(unit_a, 0.65), _analysis_item(unit_b, 0.35)],
            catalog=[unit_a, unit_b],
            rag_available=True,
            cdi=0.4,
            model=None,
        )
    )
    balanced = content_difficulty.build_content_analysis(
        content_difficulty.AnalysisBuildInput(
            items=[_analysis_item(unit_a, 0.5), _analysis_item(unit_b, 0.5)],
            catalog=[unit_a, unit_b],
            rag_available=True,
            cdi=0.4,
            model=None,
        )
    )

    assert concentrated.concentration.is_concentrated is True
    assert concentrated.concentration.top_share == pytest.approx(0.65)
    assert balanced.concentration.is_concentrated is False


def test_build_content_analysis_off_curriculum_weight_none_when_rag_unavailable():
    unit = _catalog_unit("TOAN6-A", "Tap hop", 1)

    analysis = content_difficulty.build_content_analysis(
        content_difficulty.AnalysisBuildInput(
            items=[_analysis_item(unit, 1.0, evidence=None, off_curriculum=True)],
            catalog=[unit],
            rag_available=False,
            cdi=0.4,
            model=None,
        )
    )

    assert analysis.off_curriculum_weight is None


def test_analyze_exam_paper_preserves_existing_ai_analysis_keys(monkeypatch):
    paper = ExamPaper(id=1, subject_id=1, so_school_id=1, semester_id=1, title="Test", file_url="exam.pdf", file_type=FileType.PDF, uploaded_by=1)
    paper.ai_analysis = {"source": "exam_generation"}
    subject = Subject(id=paper.subject_id, code="TOAN", name="Toan")
    catalog_unit = _catalog_unit("TOAN6-A", "Tap hop", 1)
    fake_session = MagicMock()
    fake_session.get.side_effect = lambda model, _id: {
        ExamPaper: paper,
        Subject: subject,
    }.get(model)
    monkeypatch.setattr(content_difficulty, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(content_difficulty.storage, "exam_file_path", lambda _url: "exam.pdf")
    monkeypatch.setattr(content_difficulty, "extract_exam_text", lambda *_args: "Cau 1: " * 20)
    monkeypatch.setattr(content_difficulty, "_resolve_grade_number", lambda *_args: 6)
    monkeypatch.setattr(content_difficulty, "_load_catalog", lambda *_args: [catalog_unit])
    monkeypatch.setattr(
        content_difficulty,
        "classify_competencies",
        lambda *_args: [
            content_difficulty.CompetencyGuess(
                topic="Tap hop", bloom_level=2, weight=1.0, unit_code="TOAN6-A", excerpt="Cau 1"
            )
        ],
    )
    monkeypatch.setattr(content_difficulty.retrieval, "has_rag", lambda _subject_code: True)
    monkeypatch.setattr(content_difficulty.retrieval, "rag_mon_slug", lambda _subject_code: "toan")
    monkeypatch.setattr(
        content_difficulty,
        "_collect_evidence",
        lambda *_args: ([EvidenceRef(score=0.7, heading="Bai 1", source_md="toan6.md")], True),
    )

    content_difficulty.analyze_exam_paper(paper.id)

    assert paper.ai_analysis is not None
    assert paper.ai_analysis["source"] == "exam_generation"
    assert paper.ai_analysis["content_analysis"]["version"] == 1
    assert paper.ai_analysis["content_analysis"]["items"][0]["evidence"]["score"] == 0.7
    assert paper.ai_analysis["content_analysis"]["items"][0]["off_curriculum"] is False
    fake_session.commit.assert_called_once()


def test_analyze_exam_paper_skips_when_paper_not_found(monkeypatch):
    fake_session = MagicMock()
    fake_session.get.return_value = None
    monkeypatch.setattr(content_difficulty, "SessionLocal", lambda: fake_session)

    content_difficulty.analyze_exam_paper(1)

    fake_session.commit.assert_not_called()
    fake_session.close.assert_called_once()


def test_bloom_distribution_and_alignment():
    # 40% Nhớ (Bloom 1), 30% Hiểu (Bloom 2), 20% Vận dụng (Bloom 3), 10% Phân tích/Đánh giá/Sáng tạo (Bloom 4-6)
    items = [
        content_difficulty.ResolvedCompetency(
            topic="T1", bloom_level=1, weight=0.4, unit_code="U1", unit_name="Unit 1", matched_catalog=True, unit_id=1
        ),
        content_difficulty.ResolvedCompetency(
            topic="T2", bloom_level=2, weight=0.3, unit_code="U2", unit_name="Unit 2", matched_catalog=True, unit_id=2
        ),
        content_difficulty.ResolvedCompetency(
            topic="T3", bloom_level=3, weight=0.2, unit_code="U3", unit_name="Unit 3", matched_catalog=True, unit_id=3
        ),
        content_difficulty.ResolvedCompetency(
            topic="T4", bloom_level=4, weight=0.1, unit_code="U4", unit_name="Unit 4", matched_catalog=True, unit_id=4
        ),
    ]
    dist, alignment = content_difficulty._bloom_distribution_and_alignment(items)
    assert dist["remember"] == 40.0
    assert dist["understand"] == 30.0
    assert dist["apply"] == 20.0
    assert dist["analyze"] == 10.0
    assert alignment == "ALIGNED"


def test_bloom_mapping_correctness():
    """Verify mapping 6 bậc Bloom: 1=Nhớ, 2=Hiểu, 3=Vận dụng, 4-6=Phân tích+."""
    items = [
        content_difficulty.ResolvedCompetency(
            topic="T1", bloom_level=1, weight=0.25, unit_code="U1", unit_name="Unit 1", matched_catalog=True, unit_id=1
        ),
        content_difficulty.ResolvedCompetency(
            topic="T2", bloom_level=2, weight=0.25, unit_code="U2", unit_name="Unit 2", matched_catalog=True, unit_id=2
        ),
        content_difficulty.ResolvedCompetency(
            topic="T3", bloom_level=3, weight=0.25, unit_code="U3", unit_name="Unit 3", matched_catalog=True, unit_id=3
        ),
        content_difficulty.ResolvedCompetency(
            topic="T4", bloom_level=5, weight=0.25, unit_code="U4", unit_name="Unit 4", matched_catalog=True, unit_id=4
        ),
    ]
    dist, _ = content_difficulty._bloom_distribution_and_alignment(items)
    assert dist["remember"] == 25.0
    assert dist["understand"] == 25.0
    assert dist["apply"] == 25.0
    assert dist["analyze"] == 25.0


def test_avg_retrieval_distance():
    items = [
        content_difficulty.ResolvedCompetency(
            topic="T1",
            bloom_level=1,
            weight=0.5,
            unit_code="U1",
            unit_name="Unit 1",
            matched_catalog=True,
            unit_id=1,
            evidence=EvidenceRef(score=0.8, heading="H1"),
        ),
        content_difficulty.ResolvedCompetency(
            topic="T2",
            bloom_level=3,
            weight=0.5,
            unit_code="U2",
            unit_name="Unit 2",
            matched_catalog=True,
            unit_id=2,
            evidence=EvidenceRef(score=0.6, heading="H2"),
        ),
    ]
    # score tb = 0.7 -> distance = 0.3
    assert content_difficulty._avg_retrieval_distance(items) == 0.3
