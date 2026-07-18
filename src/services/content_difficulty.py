"""Pipeline tự động tính CDI (Content Difficulty Index) cho TEVI.

Chạy nền (FastAPI BackgroundTasks) sau khi GV upload đề thi: OCR nội dung đề -> LLM gán Bloom level
theo từng chủ đề -> lưu `exam_papers.content_difficulty` + `curriculum_units`/`exam_competencies`,
để `v_exam_validity` (tam giác hóa EDI/CDI/DDI) có dữ liệu thật thay vì luôn NO_CONTENT.
"""

import json
import logging
import re
import sys
import time
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from src.db.session import SessionLocal
from src.models.enums import FileType
from src.models.tables import Class, CurriculumUnit, ExamColumnMapping, ExamCompetency, ExamPaper, Grade, Subject
from src.schemas.exam_analysis import (
    AnalysisItemRead,
    ConcentrationRead,
    CoverageRead,
    CoverageUnitRead,
    EvidenceRef,
    ExamContentAnalysis,
)
from src.services import retrieval, storage
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

# Cầu nối tạm cho MVP: tái dùng hàm OCR thuần Python của Airflow plugin (không trigger DAG, không
# phụ thuộc runtime Airflow) — package này không phải pip package nên phải tự thêm vào sys.path.
_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "pipelines" / "airflow" / "plugins"
if str(_PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGINS_DIR))

_MIN_TEXT_LAYER_CHARS = 200
_MIN_CLASSIFY_CHARS = 50
_MAX_EXCERPT_CHARS = 300
_CONCENTRATION_SHARE = 0.6
_ANALYSIS_KEY = "content_analysis"

_CLASSIFY_HEADER_LINES = [
    "Bạn là chuyên gia phân tích đề thi. Đây là nội dung 1 đề kiểm tra (tiếng Việt). Hãy tách đề thành "
    "các câu hỏi/ý lớn, với mỗi ý xác định:",
    "- topic: tên chủ đề kiến thức ngắn (vài từ)",
    "- bloom_level: mức độ theo thang Bloom, số nguyên 1-6 "
    "(1=Nhớ, 2=Hiểu, 3=Vận dụng, 4=Phân tích, 5=Đánh giá, 6=Sáng tạo)",
    "- weight: tỉ trọng điểm số của ý đó trên tổng đề (số thực 0-1, tổng các ý xấp xỉ 1)",
    "- excerpt: TRÍCH NGUYÊN VĂN 1-2 câu tiêu biểu của ý đó từ đề (không diễn đạt lại)",
]
_CLASSIFY_EXAMPLE_NO_CODE = '{"topic": "...", "bloom_level": 2, "weight": 0.3, "excerpt": "..."}'
_CLASSIFY_EXAMPLE_WITH_CODE = (
    '{"topic": "...", "bloom_level": 2, "weight": 0.3, "unit_code": "MA01" hoặc null, "excerpt": "..."}'
)


def build_classify_prompt(text: str, catalog: list[CurriculumUnit] | None = None) -> str:
    """Dựng prompt phân loại đề: luôn yêu cầu `excerpt` (trích nguyên văn, làm query RAG tốt hơn chỉ
    dùng topic); nếu có `catalog` (chuẩn CT đã seed cho môn+khối) thì ép LLM chọn `unit_code` từ danh
    sách (constrained classification) thay vì tự đặt tên chủ đề tự do -> chống phân mảnh taxonomy.
    """
    lines = list(_CLASSIFY_HEADER_LINES)
    example = _CLASSIFY_EXAMPLE_NO_CODE
    if catalog:
        catalog_lines = "\n".join(f"{u.code} — {u.name}" for u in catalog)
        lines.append(
            "- unit_code: chọn ĐÚNG 1 mã từ DANH SÁCH CHỦ ĐỀ dưới đây nếu ý thuộc chủ đề đó; nếu KHÔNG "
            f"khớp mã nào thì để null (đừng gượng ép)\n\nDANH SÁCH CHỦ ĐỀ (mã — tên):\n{catalog_lines}"
        )
        example = _CLASSIFY_EXAMPLE_WITH_CODE
    header = "\n".join(lines)
    return (
        f"{header}\n\n"
        "CHỈ trả về 1 JSON array, không giải thích, không markdown, theo đúng dạng:\n"
        f"[{example}, ...]\n\n"
        f"Nội dung đề:\n{text}"
    )


class CompetencyGuess(BaseModel):
    topic: str
    bloom_level: int = Field(ge=1, le=6)
    weight: float = Field(ge=0, le=1)
    unit_code: str | None = None
    excerpt: str | None = None


def cdi_from_bloom_mix(mix: list[tuple[int, float]]) -> float:
    """Quy đổi tổ hợp (bloom_level, weight) thành CDI 0-1 (Σbloom×weight / Σweight / 6).

    Rỗng -> 0.0; Σweight <= 0 (LLM trả toàn weight 0) -> coi weight đều thay vì chia cho 0.
    """
    if not mix:
        return 0.0
    total_weight = sum(w for _, w in mix)
    if total_weight <= 0:
        return round(sum(b for b, _ in mix) / len(mix) / 6, 3)
    return round(sum(b * w for b, w in mix) / total_weight / 6, 3)


def _slugify(text: str) -> str:
    """Chuyển chuỗi tiếng Việt thành code ngắn (a-z0-9-), dùng làm CurriculumUnit.code."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9À-ỹ]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def extract_exam_text(path: Path, file_type: FileType | None) -> str:
    """Trích text từ file đề: ưu tiên lớp text PDF (free), fallback OCR Tesseract (free) nếu quá ngắn."""
    try:
        data = path.read_bytes()
    except OSError:
        logger.warning("Không đọc được file đề: %s", path)
        return ""

    if file_type == FileType.PDF:
        text = _try_extract(lambda: _pdf_extract().extract_text_layer(data))
        if len(text) >= _MIN_TEXT_LAYER_CHARS:
            return text
        ocr_text = _try_extract(lambda: _pdf_extract().extract_with_tesseract(data, lang="vie"))
        return ocr_text if len(ocr_text) > len(text) else text

    if file_type == FileType.IMAGE:
        return _try_extract(lambda: _ocr_image_bytes(data))

    return ""


def _pdf_extract():
    from edu_pipeline import pdf_extract

    return pdf_extract


def _ocr_image_bytes(data: bytes) -> str:
    import io

    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang="vie")


def _try_extract(fn) -> str:
    try:
        return fn()
    except Exception:  # noqa: BLE001 - OCR phụ thuộc binary/thư viện ngoài, lỗi không được crash request
        logger.warning("Trích xuất nội dung đề thất bại, bỏ qua.", exc_info=True)
        return ""


def classify_competencies(text: str, catalog: list[CurriculumUnit] | None = None) -> list[CompetencyGuess]:
    """Gọi LLM tách đề thành các (chủ đề, mức Bloom, tỉ trọng, unit_code, excerpt); trả [] nếu text
    rỗng/lỗi. `catalog` (nếu có) ép LLM chọn unit_code từ chuẩn CT đã seed thay vì tự đặt tên."""
    if len(text.strip()) < _MIN_CLASSIFY_CHARS:
        return []
    try:
        response = get_llm().invoke(build_classify_prompt(text[:8000], catalog))
    except Exception:  # noqa: BLE001 - lỗi gọi LLM (auth/network/rate-limit) không được kéo sập cả pipeline
        logger.warning("Gọi LLM phân loại đề thất bại.", exc_info=True)
        return []

    try:
        raw = response.content if isinstance(response.content, str) else str(response.content)
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        items = json.loads(raw)
        guesses = [CompetencyGuess(**item) for item in items]
    except (json.JSONDecodeError, ValidationError, TypeError):
        logger.warning("Không parse được JSON phân loại đề từ LLM.", exc_info=True)
        return []

    valid_codes = {u.code for u in catalog} if catalog else set()
    for g in guesses:
        if g.unit_code is not None and g.unit_code not in valid_codes:
            logger.warning("LLM trả unit_code không có trong catalog, bỏ qua: %s", g.unit_code)
            g.unit_code = None
        if g.excerpt:
            g.excerpt = g.excerpt.strip()[:_MAX_EXCERPT_CHARS]

    total_weight = sum(g.weight for g in guesses)
    if guesses and total_weight > 0:
        for g in guesses:
            g.weight = g.weight / total_weight
    return guesses


def _resolve_grade_number(db, paper: ExamPaper) -> int | None:
    if paper.grade_id is not None:
        grade = db.get(Grade, paper.grade_id)
        return grade.grade_number if grade else None
    mapping = db.execute(select(ExamColumnMapping).where(ExamColumnMapping.exam_paper_id == paper.id)).scalars().first()
    if mapping is None or mapping.class_id is None:
        return None
    klass = db.get(Class, mapping.class_id)
    if klass is None:
        return None
    grade = db.get(Grade, klass.grade_id)
    return grade.grade_number if grade else None


def _get_or_create_unit(db, subject_id: UUID, grade_number: int, code: str, name: str) -> CurriculumUnit:
    unit = db.execute(
        select(CurriculumUnit).where(
            CurriculumUnit.subject_id == subject_id,
            CurriculumUnit.grade_number == grade_number,
            CurriculumUnit.code == code,
        )
    ).scalar_one_or_none()
    if unit is None:
        unit = CurriculumUnit(subject_id=subject_id, grade_number=grade_number, code=code, name=name)
        db.add(unit)
        db.flush()
    return unit


def _load_catalog(db, subject_id: UUID, grade_number: int | None) -> list[CurriculumUnit]:
    """Chuẩn CT (chương/bài) đã seed sẵn cho (môn, khối) — rỗng nếu chưa seed hoặc chưa rõ khối."""
    if grade_number is None:
        return []
    stmt = select(CurriculumUnit).where(
        CurriculumUnit.subject_id == subject_id,
        CurriculumUnit.grade_number == grade_number,
    )
    return list(db.execute(stmt).scalars().all())


class ResolvedCompetency(BaseModel):
    """1 ý của đề sau khi neo taxonomy (+ bằng chứng SGK nếu có ở bước sau) — input dựng ai_analysis."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    topic: str
    excerpt: str | None
    bloom_level: int
    weight: float
    unit_id: UUID | None
    unit_code: str | None
    unit_name: str | None
    matched_catalog: bool
    evidence: EvidenceRef | None = None
    off_curriculum: bool | None = None


class AnalysisContext(BaseModel):
    """Gom tham số cho _resolve_units (giữ quy ước ≤3 tham số/hàm)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject_id: UUID
    subject_code: str
    grade_number: int | None
    catalog: dict[str, CurriculumUnit]


class AnalysisBuildInput(BaseModel):
    """Input thuần để dựng `ai_analysis.content_analysis` v1."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[ResolvedCompetency]
    catalog: list[CurriculumUnit]
    rag_available: bool
    cdi: float
    model: str | None


def _resolve_units(db, ctx: AnalysisContext, guesses: list[CompetencyGuess]) -> list[ResolvedCompetency]:
    """Neo mỗi ý vào CurriculumUnit: unit_code khớp catalog -> lookup trực tiếp (không query thêm);
    không khớp + biết khối -> fallback tạo unit từ topic (hành vi cũ, chấp nhận phân mảnh cho
    môn/khối chưa seed catalog); không biết khối -> unit_id=None (không ghi exam_competencies)."""
    resolved: list[ResolvedCompetency] = []
    for g in guesses:
        unit = ctx.catalog.get(g.unit_code) if g.unit_code else None
        matched = unit is not None
        if unit is None and ctx.grade_number is not None:
            unit = _get_or_create_unit(db, ctx.subject_id, ctx.grade_number, _slugify(g.topic)[:50], g.topic)
        resolved.append(
            ResolvedCompetency(
                topic=g.topic,
                excerpt=g.excerpt,
                bloom_level=g.bloom_level,
                weight=g.weight,
                unit_id=unit.id if unit else None,
                unit_code=unit.code if unit else None,
                unit_name=unit.name if unit else None,
                matched_catalog=matched,
            )
        )
    return resolved


def merge_by_unit(items: list[ResolvedCompetency]) -> dict[UUID, tuple[int, float]]:
    """Gộp các ý cùng unit trước khi ghi exam_competencies (PK = exam_paper_id + unit_id, và nhiều ý
    thường map cùng 1 unit khi taxonomy neo theo catalog nhỏ): weight = TỔNG; bloom_level = trung
    bình có trọng số làm tròn half-up (Σweight=0 trong nhóm -> mean đơn giản). Bỏ ý không có unit_id."""
    groups: dict[UUID, list[ResolvedCompetency]] = {}
    for it in items:
        if it.unit_id is None:
            continue
        groups.setdefault(it.unit_id, []).append(it)

    merged: dict[UUID, tuple[int, float]] = {}
    for unit_id, group in groups.items():
        total_weight = sum(it.weight for it in group)
        if total_weight > 0:
            bloom_mean = sum(it.bloom_level * it.weight for it in group) / total_weight
        else:
            bloom_mean = sum(it.bloom_level for it in group) / len(group)
        merged[unit_id] = (int(bloom_mean + 0.5), round(total_weight, 3))
    return merged


def _evidence_query(guess: CompetencyGuess) -> str:
    """Query RAG cho 1 ý: topic + excerpt (nếu có) — sát nghĩa hơn chỉ dùng topic vài từ."""
    return f"{guess.topic}. {guess.excerpt}" if guess.excerpt else guess.topic


def _best_evidence(query: str, mon: str, lop: str) -> EvidenceRef | None:
    """Hit SGK tốt nhất cho 1 ý (Qdrant đã sort theo score desc + áp `retrieval_score_floor`) —
    None nghĩa là không có bằng chứng nào đạt ngưỡng (ứng viên "ngoài chương trình")."""
    hits = retrieval.search_textbook(query, mon=mon, lop=lop)
    if not hits:
        return None
    top = hits[0]
    return EvidenceRef(score=top["score"], heading=top.get("heading") or None, source_md=top.get("source_md") or None)


def _collect_evidence(guesses: list[CompetencyGuess], mon: str, lop: str) -> tuple[list[EvidenceRef | None], bool]:
    """Bằng chứng SGK cho từng ý, theo ĐÚNG thứ tự `guesses`. Trả (evidences, rag_available) —
    sidecar/Qdrant lỗi giữa chừng -> ([None]*n, False) deterministic, KHÔNG raise (fail-soft,
    pipeline nền không được sập vì RAG tạm gián đoạn)."""
    try:
        return [_best_evidence(_evidence_query(g), mon, lop) for g in guesses], True
    except retrieval.RetrievalUnavailableError:
        logger.warning("RAG evidence không khả dụng, bỏ qua bước đối chiếu SGK cho đề.")
        return [None] * len(guesses), False


def _analysis_items(items: list[ResolvedCompetency]) -> list[AnalysisItemRead]:
    return [
        AnalysisItemRead(
            topic=item.topic,
            excerpt=item.excerpt,
            unit_code=item.unit_code,
            unit_name=item.unit_name,
            matched_catalog=item.matched_catalog,
            bloom_level=item.bloom_level,
            weight=item.weight,
            evidence=item.evidence,
            off_curriculum=item.off_curriculum,
        )
        for item in items
    ]


def _catalog_weights(items: list[ResolvedCompetency]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for item in items:
        if item.matched_catalog and item.unit_code:
            weights[item.unit_code] = weights.get(item.unit_code, 0.0) + item.weight
    return weights


def _coverage(items: list[ResolvedCompetency], catalog: list[CurriculumUnit]) -> tuple[CoverageRead, list[CoverageUnitRead]]:
    weights = _catalog_weights(items)
    units = [CoverageUnitRead(unit_code=u.code, unit_name=u.name, weight=round(weights.get(u.code, 0.0), 3)) for u in catalog]
    total = len(catalog)
    matched = sum(1 for u in catalog if weights.get(u.code, 0.0) > 0)
    return CoverageRead(catalog_total=total, matched=matched, ratio=matched / total if total else None), units


def _unit_display(items: list[ResolvedCompetency], unit_code: str) -> tuple[str | None, str | None]:
    for item in items:
        if item.unit_code == unit_code:
            return item.unit_code, item.unit_name
    return None, None


def _concentration(items: list[ResolvedCompetency]) -> ConcentrationRead:
    weights: dict[str, float] = {}
    for item in items:
        if item.unit_code:
            weights[item.unit_code] = weights.get(item.unit_code, 0.0) + item.weight
    total = sum(weights.values())
    if not weights or total <= 0:
        return ConcentrationRead(top_unit_code=None, top_unit_name=None, top_share=None, is_concentrated=False)
    top_code, top_weight = max(weights.items(), key=lambda pair: pair[1])
    top_share = top_weight / total
    unit_code, unit_name = _unit_display(items, top_code)
    return ConcentrationRead(
        top_unit_code=unit_code,
        top_unit_name=unit_name,
        top_share=top_share,
        is_concentrated=top_share > _CONCENTRATION_SHARE,
    )


def build_content_analysis(inp: AnalysisBuildInput) -> ExamContentAnalysis:
    """Dựng JSON phân tích nội dung v1.

    Coverage chỉ tính ý khớp catalog và liệt kê đủ mọi unit catalog, kể cả weight=0. Concentration gom
    theo unit_code của toàn bộ ý đã resolve, gồm cả unit fallback ngoài catalog. off_curriculum_weight
    chỉ có ý nghĩa khi RAG khả dụng; nếu không, trả None để tránh kết luận nhầm ngoài chương trình.
    """
    coverage, coverage_units = _coverage(inp.items, inp.catalog)
    off_weight = None
    if inp.rag_available:
        off_weight = round(sum(item.weight for item in inp.items if item.off_curriculum), 3)
    return ExamContentAnalysis(
        model=inp.model,
        cdi=inp.cdi,
        rag_available=inp.rag_available,
        items=_analysis_items(inp.items),
        coverage=coverage,
        coverage_units=coverage_units,
        concentration=_concentration(inp.items),
        off_curriculum_weight=off_weight,
    )


def _collect_evidence_for_context(
    ctx: AnalysisContext, guesses: list[CompetencyGuess]
) -> tuple[list[EvidenceRef | None], bool]:
    if not retrieval.has_rag(ctx.subject_code) or ctx.grade_number is None:
        return [None] * len(guesses), False
    return _collect_evidence(guesses, retrieval.rag_mon_slug(ctx.subject_code), str(ctx.grade_number))


def _attach_evidence(
    resolved: list[ResolvedCompetency], evidences: list[EvidenceRef | None], rag_available: bool
) -> list[ResolvedCompetency]:
    """Gắn bằng chứng RAG vào từng ý. off_curriculum: True (không có evidence dù đã tra RAG),
    False (có evidence, đúng chương trình), None (RAG không khả dụng -> chưa xác định được)."""
    return [
        item.model_copy(update={"evidence": evidence, "off_curriculum": (evidence is None) if rag_available else None})
        for item, evidence in zip(resolved, evidences, strict=False)
    ]


def _persist_competencies(db, paper_id: UUID, merged: dict[UUID, tuple[int, float]]) -> None:
    """Ghi exam_competencies từ kết quả merge_by_unit — xóa hết rồi insert lại (đề không quá nhiều
    ý nên không cần diff, và PK exam_paper_id+unit_id đã được merge_by_unit khử trùng trước đó)."""
    db.execute(ExamCompetency.__table__.delete().where(ExamCompetency.exam_paper_id == paper_id))
    for unit_id, (bloom_level, weight) in merged.items():
        db.add(ExamCompetency(exam_paper_id=paper_id, unit_id=unit_id, weight=weight, bloom_level=bloom_level))


def analyze_exam_paper(exam_paper_id: UUID) -> None:
    """Phân tích nội dung 1 đề thi và lưu CDI — chạy nền qua BackgroundTasks, không raise ra ngoài."""
    db = SessionLocal()
    t_start = time.monotonic()
    try:
        paper = db.get(ExamPaper, exam_paper_id)
        if paper is None:
            return

        t0 = time.monotonic()
        text = extract_exam_text(storage.exam_file_path(paper.file_url), paper.file_type)
        logger.info("CDI[%s] trích text: %.2fs (%d ký tự)", exam_paper_id, time.monotonic() - t0, len(text))

        # Resolve khối + tải catalog TRƯỚC khi gọi LLM phân loại -> constrained classification.
        grade_number = _resolve_grade_number(db, paper)
        subject = db.get(Subject, paper.subject_id)
        catalog = _load_catalog(db, paper.subject_id, grade_number)

        t0 = time.monotonic()
        guesses = classify_competencies(text, catalog)
        logger.info("CDI[%s] gọi LLM phân loại: %.2fs (%d ý)", exam_paper_id, time.monotonic() - t0, len(guesses))
        if not guesses:
            paper.content_analyzed_at = _now()
            paper.content_source = paper.file_type
            db.commit()
            return

        ctx = AnalysisContext(
            subject_id=paper.subject_id,
            subject_code=subject.code if subject else "",
            grade_number=grade_number,
            catalog={u.code: u for u in catalog},
        )
        resolved = _resolve_units(db, ctx, guesses)
        evidences, rag_available = _collect_evidence_for_context(ctx, guesses)
        resolved = _attach_evidence(resolved, evidences, rag_available)
        if grade_number is not None:
            _persist_competencies(db, paper.id, merge_by_unit(resolved))
        else:
            logger.warning("Đề %s không xác định được khối -> chỉ lưu CDI, không tạo CurriculumUnit.", paper.id)

        paper.content_difficulty = cdi_from_bloom_mix([(g.bloom_level, g.weight) for g in guesses])
        analysis = build_content_analysis(
            AnalysisBuildInput(
                items=resolved,
                catalog=catalog,
                rag_available=rag_available,
                cdi=paper.content_difficulty,
                model=None,
            )
        )
        paper.ai_analysis = {**(paper.ai_analysis or {}), _ANALYSIS_KEY: analysis.model_dump(mode="json")}
        paper.content_analyzed_at = _now()
        paper.content_source = paper.file_type
        db.commit()
    except Exception:  # noqa: BLE001 - lỗi nền không được làm crash app
        logger.exception("Lỗi khi phân tích CDI cho đề %s", exam_paper_id)
        db.rollback()
    finally:
        logger.info("CDI[%s] tổng thời gian: %.2fs", exam_paper_id, time.monotonic() - t_start)
        db.close()


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
