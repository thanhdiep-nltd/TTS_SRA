"""Pipeline tự động phân tích nội dung đề thi (M1+M2+M3 — docs_vsf/plan_cdi_kg_anchored.md).

Chạy nền (FastAPI BackgroundTasks) sau khi GV upload đề thi:
  VLM đọc đề (giữ LaTeX) → LLM decompose + map mỗi ý vào 1–3 node của catalog phẳng
  (curriculum_units, lọc môn/khối/học kỳ) → ghi exam_competencies → tính 5 trục
  (CDI/Bloom, Coverage, Concentration, Off-curriculum, Evidence = chương/bài từ cây).

KHÔNG còn full-text RAG làm thẩm phán (bỏ cosine/evidence SGK) — off-curriculum do LLM
map null quyết định; trích dẫn đọc tĩnh từ cây (parent_id).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import or_, select

from src.db.session import SessionLocal
from src.models.enums import FileType
from src.models.tables import Class, CurriculumUnit, ExamColumnMapping, ExamCompetency, ExamPaper, Grade
from src.schemas.exam_analysis import (
    AnalysisItemRead,
    ConcentrationRead,
    CoverageRead,
    CoverageUnitRead,
    ExamContentAnalysis,
    NodeRef,
)
from src.services import storage, vlm
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

# Cầu nối tạm cho MVP: tái dùng hàm OCR thuần Python của Airflow plugin (không trigger DAG, không
# phụ thuộc runtime Airflow) — package này không phải pip package nên phải tự thêm vào sys.path.
_PLUGINS_DIR = Path(__file__).resolve().parents[2] / "pipelines" / "airflow" / "plugins"
if str(_PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGINS_DIR))

_MIN_TEXT_LAYER_CHARS = 200
# Chặn text rác/trống nhưng KHÔNG chặn câu hỏi ngắn hợp lệ (vd "Tính 2/3 + 1/4." = 16 ký tự) —
# guard 50 trước đây khiến câu ngắn bị bỏ sót (eval null-rate giả tạo cao).
_MIN_CLASSIFY_CHARS = 10
_MAX_EXCERPT_CHARS = 300
_MAX_NODES_PER_ITEM = 3
_CONCENTRATION_SHARE = 0.6
_MAX_SHORTLIST = 60
_ANALYSIS_KEY = "content_analysis"


class NodeWeight(BaseModel):
    """1 node kiến thức + tỉ trọng điểm trong 1 ý."""

    node_id: int
    weight: float = Field(ge=0.0, le=1.0)


class MappedItem(BaseModel):
    """1 ý của đề sau khi LLM map: 1–3 node kèm weight; off_curriculum_weight = phần không map được."""

    topic: str
    nodes: list[NodeWeight] = []
    bloom_level: int = Field(ge=1, le=6)
    off_curriculum_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    excerpt: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = None
    candidates: list[int] = []  # node_id gợi ý cho GV chốt khi nodes rỗng


class ResolvedCompetency(BaseModel):
    """1 ý sau khi neo vào node + thông tin cây (chương/bài) — input dựng ai_analysis."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    topic: str
    excerpt: str | None = None
    bloom_level: int
    weight: float
    unit_id: int | None = None
    unit_code: str | None = None
    unit_name: str | None = None
    matched_catalog: bool = False
    off_curriculum: bool | None = None
    off_curriculum_weight: float = 0.0
    chapter: str | None = None
    lesson: str | None = None
    candidates: list[int] = []


class AnalysisBuildInput(BaseModel):
    """Input thuần để dựng ai_analysis.content_analysis (5 trục)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[ResolvedCompetency]
    catalog: list[CurriculumUnit]
    cdi: float
    model: str | None


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


def extract_exam_text(path: Path, file_type: FileType | None) -> str:
    """Trích text từ file đề: lớp text PDF (free) → VLM đọc trang/ảnh (giữ LaTeX) → fallback OCR.

    M1 trong plan_cdi_kg_anchored.md: VLM (Qwen3-VL-Flash) thay OCR thô cho phần công thức.
    Khi VLM chưa có key/lỗi → fallback OCR cũ (không chặn pipeline).
    """
    try:
        data = path.read_bytes()
    except OSError:
        logger.warning("Không đọc được file đề: %s", path)
        return ""

    if file_type == FileType.PDF:
        text = _try_extract(lambda: _pdf_extract().extract_text_layer(data))
        if len(text) >= _MIN_TEXT_LAYER_CHARS:
            return text
        vlm_text = _try_extract(lambda: vlm.read_pdf_pages(path))
        if len(vlm_text) > len(text):
            return vlm_text
        ocr_text = _try_extract(lambda: _pdf_extract().extract_with_tesseract(data, lang="vie"))
        return ocr_text if len(ocr_text) > len(text) else text

    if file_type == FileType.IMAGE:
        vlm_text = _try_extract(lambda: vlm.read_image_bytes(data))
        if vlm_text:
            return vlm_text
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
    except Exception:  # noqa: BLE001 - OCR/VLM phụ thuộc binary/thư viện ngoài, lỗi không được crash request
        logger.warning("Trích xuất nội dung đề thất bại, bỏ qua.", exc_info=True)
        return ""


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


def build_shortlist(db, subject_id: int, grade_number: int | None, semester_number: int | None) -> list[CurriculumUnit]:
    """Lọc catalog phẳng active theo (môn, khối, học kỳ) → shortlist node cho LLM map."""
    stmt = select(CurriculumUnit).where(
        CurriculumUnit.subject_id == subject_id,
        CurriculumUnit.is_active.is_(True),
    )
    if grade_number is not None:
        stmt = stmt.where(CurriculumUnit.grade_number == grade_number)
    if semester_number in (1, 2):
        stmt = stmt.where(
            or_(CurriculumUnit.semester_number.is_(None), CurriculumUnit.semester_number == semester_number)
        )
    units = list(db.execute(stmt.order_by(CurriculumUnit.grade_number, CurriculumUnit.code)).scalars().all())
    if len(units) > _MAX_SHORTLIST:
        logger.warning("shortlist_wide: %d node subject=%s grade=%s", len(units), subject_id, grade_number)
    return units


def build_node_listing(shortlist: list[CurriculumUnit]) -> str:
    """Danh sách node dạng "id: tên (khối, HK)" cho prompt — LLM chọn node_id từ đây."""
    return "\n".join(
        f"- {unit.id}: {unit.name} (khối {unit.grade_number}"
        + (f", HK{unit.semester_number}" if unit.semester_number else "")
        + ")"
        for unit in shortlist
    )


_MAP_HEADER_LINES = [
    "Bạn là chuyên gia phân tích đề thi. Tách đề dưới đây thành các câu hỏi/ý lớn, với MỖI Ý xác định:",
    "- nodes: chọn 1–3 node kiến thức từ DANH SÁCH (node_id) mà ý kiểm tra; mỗi node kèm weight (0..1) là tỉ trọng điểm của phần kiến thức đó trong ý",
    "- off_curriculum_weight: tỉ trọng phần kiến thức của ý KHÔNG nằm trong danh sách (0..1). Toàn bộ ngoài danh sách → nodes = [] và off_curriculum_weight = 1",
    "- bloom_level: mức Bloom CỦA CẢ Ý (1=Nhớ, 2=Hiểu, 3=Vận dụng, 4=Phân tích, 5=Đánh giá, 6=Sáng tạo)",
    "- excerpt: TRÍCH NGUYÊN VĂN 1–2 câu tiêu biểu của ý từ đề (không diễn đạt lại)",
    "- confidence: 0..1 mức tự tin; reason: 1 câu giải thích vì sao chọn node đó",
]


def build_map_prompt(text: str, shortlist: list[CurriculumUnit]) -> str:
    """Dựng prompt constrained: LLM chọn node_id TỪ shortlist (không tự đặt tên chủ đề)."""
    lines = list(_MAP_HEADER_LINES)
    if shortlist:
        lines.append(f"\nDANH SÁCH NODE:\n{build_node_listing(shortlist)}")
    example = (
        '[{"topic": "...", "nodes": [{"node_id": 1, "weight": 0.6}, {"node_id": 2, "weight": 0.4}], '
        '"bloom_level": 3, "off_curriculum_weight": 0.0, "excerpt": "...", "confidence": 0.8, "reason": "..."}]'
    )
    return "\n".join(lines) + f"\n\nCHỈ trả về 1 JSON array, không giải thích, không markdown:\n{example}\n\nNội dung đề:\n{text}"


def parse_mapped_items(raw: str, valid_ids: set[int]) -> list[MappedItem]:
    """Parse JSON array → MappedItem; bỏ node ngoài shortlist (chuyển trọng số sang off); chuẩn hóa Σ=1."""
    try:
        cleaned = re.sub(r"^\`\`\`(?:json)?|\`\`\`$", "", raw.strip(), flags=re.MULTILINE).strip()
        parsed = [MappedItem(**item) for item in json.loads(cleaned)]
    except (json.JSONDecodeError, ValidationError, TypeError):
        logger.warning("Không parse được JSON map đề từ LLM.", exc_info=True)
        return []

    result: list[MappedItem] = []
    for item in parsed:
        kept = [node for node in item.nodes if node.node_id in valid_ids]
        off = item.off_curriculum_weight + sum(n.weight for n in item.nodes if n.node_id not in valid_ids)
        if len(kept) > _MAX_NODES_PER_ITEM:
            off += sum(n.weight for n in kept[_MAX_NODES_PER_ITEM:])
            kept = kept[:_MAX_NODES_PER_ITEM]
        total = sum(n.weight for n in kept) + off
        if total > 0 and abs(total - 1.0) > 1e-6:
            kept = [NodeWeight(node_id=n.node_id, weight=round(n.weight / total, 4)) for n in kept]
            off = round(off / total, 4)
        result.append(item.model_copy(update={"nodes": kept, "off_curriculum_weight": round(off, 4)}))
    return result


def _invoke_map(model: Any, text: str, shortlist: list[CurriculumUnit]) -> str:
    """Gọi LLM 1 lần trả raw JSON; lỗi → "" (không crash pipeline nền)."""
    try:
        response = model.invoke(build_map_prompt(text[:8000], shortlist))
    except Exception:  # noqa: BLE001 - lỗi LLM (auth/network/rate-limit) không kéo sập pipeline
        logger.warning("Gọi LLM map đề thất bại.", exc_info=True)
        return ""
    return response.content if isinstance(response.content, str) else str(response.content)


def map_items(text: str, shortlist: list[CurriculumUnit], llm: Any | None = None) -> list[MappedItem]:
    """LLM decompose đề + map mỗi ý vào 1–3 node trong shortlist; retry 1 lần khi parse hỏng."""
    if len(text.strip()) < _MIN_CLASSIFY_CHARS:
        return []
    model = llm or get_llm()
    valid_ids = {unit.id for unit in shortlist}
    items = parse_mapped_items(_invoke_map(model, text, shortlist), valid_ids)
    if not items:
        items = parse_mapped_items(_invoke_map(model, text, shortlist), valid_ids)
    return items


def rejudge_null_items(
    items: list[MappedItem], shortlist: list[CurriculumUnit], llm: Any | None = None
) -> list[MappedItem]:
    """Vòng 2 cho ý không map được node nào: LLM xem lại kèm lý do; vẫn null → candidates cho GV chốt."""
    nulls = [item for item in items if not item.nodes]
    if not nulls:
        return items
    model = llm or get_llm()
    valid_ids = {unit.id for unit in shortlist}
    prompt = (
        "Các ý sau bị đánh giá 'ngoài chương trình' (không khớp node nào trong danh sách). "
        "Xem lại THẬT KỸ: nếu ý thực chất thuộc node nào đó (dù diễn đạt khác / đổi ngữ cảnh đời thực) "
        "thì map lại đúng format JSON array như trước; nếu thật sự ngoài chương trình thì giữ nodes = [] "
        f"và off_curriculum_weight = 1.\n\nDANH SÁCH NODE:\n{build_node_listing(shortlist)}\n\nCác ý cần xem lại:\n"
        + "\n".join(f"- {item.topic}: {item.excerpt or ''} ({item.reason or 'không có lý do'})" for item in nulls)
    )
    second = parse_mapped_items(_invoke_map(model, prompt, shortlist), valid_ids)
    by_topic = {item.topic: item for item in second}
    result: list[MappedItem] = []
    for item in items:
        if item.nodes:
            result.append(item)
            continue
        replacement = by_topic.get(item.topic)
        if replacement is not None and replacement.nodes:
            result.append(replacement)
        else:
            result.append(item.model_copy(update={"candidates": [unit.id for unit in shortlist[:3]]}))
    return result


def _normalize_resolved(
    resolved: list[ResolvedCompetency], items: list[MappedItem]
) -> tuple[list[ResolvedCompetency], list[MappedItem]]:
    """Chuẩn hóa weight về tổng đề = 1 (weight trong prompt là tỉ trọng TRONG ý, Σ/ý ≈ 1).

    Cần thiết để exam_competencies.weight ∈ [0,1] (CHECK constraint) và CDI/coverage/concentration
    dùng trọng số so sánh được giữa các ý. Không đổi nếu tổng đã ≈ 1.
    """
    total = sum(r.weight for r in resolved) + sum(it.off_curriculum_weight for it in items)
    if total <= 0 or abs(total - 1.0) < 1e-6:
        return resolved, items
    scale = 1.0 / total
    for r in resolved:
        r.weight = round(r.weight * scale, 4)
    for it in items:
        it.off_curriculum_weight = round(it.off_curriculum_weight * scale, 4)
    return resolved, items


def _expand_mapped(items: list[MappedItem], shortlist: list[CurriculumUnit]) -> list[ResolvedCompetency]:
    """Mỗi MappedItem → nhiều ResolvedCompetency (1/node); chapter/lesson resolve từ cây (parent_id)."""
    by_id = {unit.id: unit for unit in shortlist}
    resolved: list[ResolvedCompetency] = []
    for item in items:
        for node in item.nodes:
            unit = by_id.get(node.node_id)
            if unit is None:
                continue
            parent = by_id.get(unit.parent_id) if unit.parent_id else None
            chapter = parent.name if parent else (unit.name if unit.parent_id is None else None)
            lesson = unit.name if unit.parent_id is not None else None
            resolved.append(
                ResolvedCompetency(
                    topic=item.topic,
                    excerpt=item.excerpt,
                    bloom_level=item.bloom_level,
                    weight=node.weight,
                    unit_id=unit.id,
                    unit_code=unit.code,
                    unit_name=unit.name,
                    matched_catalog=True,
                    off_curriculum=False,
                    off_curriculum_weight=0.0,
                    chapter=chapter,
                    lesson=lesson,
                    candidates=item.candidates,
                )
            )
    return resolved


def merge_by_unit(items: list[ResolvedCompetency]) -> dict[int, tuple[int, float]]:
    """Gộp các ý cùng unit trước khi ghi exam_competencies: weight = TỔNG; bloom = trung bình có trọng số."""
    groups: dict[int, list[ResolvedCompetency]] = {}
    for it in items:
        if it.unit_id is None:
            continue
        groups.setdefault(it.unit_id, []).append(it)

    merged: dict[int, tuple[int, float]] = {}
    for unit_id, group in groups.items():
        total_weight = sum(it.weight for it in group)
        if total_weight > 0:
            bloom_mean = sum(it.bloom_level * it.weight for it in group) / total_weight
        else:
            bloom_mean = sum(it.bloom_level for it in group) / len(group)
        merged[unit_id] = (int(bloom_mean + 0.5), round(total_weight, 3))
    return merged


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
            node_ref=NodeRef(node_id=item.unit_id, chapter=item.chapter, lesson=item.lesson) if item.unit_id else None,
            off_curriculum=item.off_curriculum,
            off_curriculum_weight=item.off_curriculum_weight,
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


def _bloom_distribution_and_alignment(items: list[ResolvedCompetency]) -> tuple[dict[str, float], str]:
    """Tính phân bố Bloom (chuẩn tham chiếu 40/30/20/10) và đánh giá độ lệch."""
    total_w = sum(it.weight for it in items)
    if total_w <= 0:
        return {"remember": 0.0, "understand": 0.0, "apply": 0.0, "analyze": 0.0}, "ALIGNED"

    rem_w = sum(it.weight for it in items if it.bloom_level == 1)
    und_w = sum(it.weight for it in items if it.bloom_level == 2)
    app_w = sum(it.weight for it in items if it.bloom_level == 3)
    anz_w = sum(it.weight for it in items if it.bloom_level >= 4)

    rem_pct = round(rem_w / total_w * 100, 1)
    und_pct = round(und_w / total_w * 100, 1)
    app_pct = round(app_w / total_w * 100, 1)
    anz_pct = round(anz_w / total_w * 100, 1)

    dist = {"remember": rem_pct, "understand": und_pct, "apply": app_pct, "analyze": anz_pct}
    hard_score = app_pct + anz_pct
    if hard_score > 45.0:
        alignment = "BIASED_HARD"
    elif hard_score < 15.0:
        alignment = "BIASED_EASY"
    else:
        alignment = "ALIGNED"
    return dist, alignment


def build_content_analysis(inp: AnalysisBuildInput) -> ExamContentAnalysis:
    """Dựng JSON phân tích nội dung theo 5 trục (bỏ Semantic Distance — plan PHẦN C)."""
    coverage, coverage_units = _coverage(inp.items, inp.catalog)
    off_weight = round(sum(item.off_curriculum_weight for item in inp.items), 3)
    bloom_dist, bloom_align = _bloom_distribution_and_alignment(inp.items)
    return ExamContentAnalysis(
        model=inp.model,
        cdi=inp.cdi,
        items=_analysis_items(inp.items),
        coverage=coverage,
        coverage_units=coverage_units,
        concentration=_concentration(inp.items),
        off_curriculum_weight=off_weight,
        bloom_distribution=bloom_dist,
        bloom_alignment=bloom_align,
    )


def _persist_competencies(db, paper_id: int, merged: dict[int, tuple[int, float]]) -> None:
    """Ghi exam_competencies từ kết quả merge_by_unit — xóa hết rồi insert lại."""
    db.execute(ExamCompetency.__table__.delete().where(ExamCompetency.exam_paper_id == paper_id))
    for unit_id, (bloom_level, weight) in merged.items():
        db.add(ExamCompetency(exam_paper_id=paper_id, unit_id=unit_id, weight=weight, bloom_level=bloom_level))


def analyze_exam_paper(exam_paper_id: int) -> None:
    """Phân tích nội dung 1 đề thi (M1+M2+M3) — chạy nền qua BackgroundTasks, không raise ra ngoài."""
    db = SessionLocal()
    t_start = time.monotonic()
    try:
        paper = db.get(ExamPaper, exam_paper_id)
        if paper is None:
            return

        t0 = time.monotonic()
        text = extract_exam_text(storage.exam_file_path(paper.file_url), paper.file_type)
        logger.info("CDI[%s] trích text: %.2fs (%d ký tự)", exam_paper_id, time.monotonic() - t0, len(text))

        grade_number = _resolve_grade_number(db, paper)
        semester = paper.semester_id if paper.semester_id in (1, 2) else None
        shortlist = build_shortlist(db, paper.subject_id, grade_number, semester)

        t0 = time.monotonic()
        items = map_items(text, shortlist)
        logger.info("CDI[%s] LLM map: %.2fs (%d ý)", exam_paper_id, time.monotonic() - t0, len(items))
        if not items:
            paper.content_analyzed_at = _now()
            paper.content_source = paper.file_type
            db.commit()
            return

        items = rejudge_null_items(items, shortlist)
        resolved = _expand_mapped(items, shortlist)
        resolved, items = _normalize_resolved(resolved, items)
        merged = merge_by_unit(resolved)
        if merged:
            _persist_competencies(db, paper.id, merged)
        else:
            logger.warning("Đề %s không map được node nào.", paper.id)

        paper.content_difficulty = cdi_from_bloom_mix([(item.bloom_level, item.weight) for item in resolved])
        analysis = build_content_analysis(
            AnalysisBuildInput(items=resolved, catalog=shortlist, cdi=paper.content_difficulty, model=None)
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
