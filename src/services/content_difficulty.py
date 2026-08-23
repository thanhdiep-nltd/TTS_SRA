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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
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
    confidence: float | None = None
    reason: str | None = None
    image_url: str | None = None
    has_figure: bool | None = None
    question_share: float | None = None
    is_primary: bool | None = None


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
    # exam_papers.grade_id là Integer lưu grade_number (VD: 6 = Khối 6) — không phải UUID.
    if paper.grade_id is not None:
        return paper.grade_id
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
        CurriculumUnit.is_phu.is_(False),  # node phụ (Ôn tập/Kiểm tra/Hoạt động) không map đề thi
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
    """Danh sách node dạng "id: tên (khối, HK) — Từ khóa: ... — Tóm tắt: ..." cho prompt.

    Node có nội dung làm giàu (keywords/summary khi nạp sách) sẽ kèm thêm — giúp LLM map
    đề chọn đúng node theo nội dung, không chỉ tên. Giới hạn độ dài để không phình prompt.
    """
    lines: list[str] = []
    for unit in shortlist:
        line = (
            f"- {unit.id}: {unit.name} (khối {unit.grade_number}"
            + (f", HK{unit.semester_number}" if unit.semester_number else "")
            + ")"
        )
        if unit.keywords:
            line += " — Từ khóa: " + ", ".join(unit.keywords[:5])
        if unit.summary:
            summary = unit.summary.strip()
            if len(summary) > 120:
                summary = summary[:117].rstrip() + "..."
            line += " — " + summary
        lines.append(line)
    return "\n".join(lines)


_MAP_HEADER_LINES = [
    "Bạn là chuyên gia khảo thí và phân tích chuẩn ma trận đề thi. Dưới lăng kính của KHUNG CHƯƠNG TRÌNH HỌC được cung cấp (DANH SÁCH NODE), hãy đối chiếu nội dung đề thi/câu hỏi để phân tích thành các ĐƠN VỊ ĐÁNH GIÁ ĐỘC LẬP (mỗi đơn vị là một nhiệm vụ giải quyết vấn đề chứa đựng các yếu tố tri thức của một chương hoặc cụm chương cụ thể).",
    "Với MỖI ĐƠN VỊ ĐÁNH GIÁ, hãy xác định:",
    "- topic: mô tả ngắn gọn trọng tâm năng lực hoặc nhiệm vụ gắn với chuyên đề kiến thức cần thực hiện",
    "- excerpt: TRÍCH NGUYÊN VĂN phần nội dung hoặc yêu cầu tương ứng từ đề bài",
    "- nodes: danh sách các đơn vị kiến thức từ DANH SÁCH (node_id) là NỘI DUNG ĐÁNH GIÁ CỐT LÕI (Focal Targets) của nhiệm vụ này. Mỗi node kèm weight (0..1) là tỉ trọng đóng góp thực chất của đơn vị tri thức đó:",
    "  + NGUYÊN TẮC HỘI TỤ TRỌNG TÂM: Ưu tiên chọn ĐÚNG 1 NODE KIẾN THỨC LÀ ĐỐI TƯỢNG ĐÁNH GIÁ CỐT LÕI NHẤT (weight = 1.0). KHÔNG gán các kỹ năng thao tác nền tảng hay công cụ phụ trợ hiển nhiên được dùng làm phương tiện.",
    "  + Chỉ phân rã từ 2 node trở lên khi câu hỏi có từ 2 yêu cầu/ý hỏi độc lập (ví dụ ý a, ý b) hoặc kết hợp liên chuyên đề rõ rệt (mỗi node tối thiểu weight >= 0.3, tổng weight = 1.0 - off_curriculum_weight).",
    "- off_curriculum_weight: tỉ trọng phần kiến thức nằm ngoài danh sách chương trình (0..1). Toàn bộ ngoài danh sách → nodes = [] và off_curriculum_weight = 1.0",
    "- bloom_level: mức độ nhận thức Bloom của nhiệm vụ (1=Nhớ, 2=Hiểu, 3=Vận dụng, 4=Phân tích, 5=Đánh giá, 6=Sáng tạo)",
    "- confidence: 0..1 mức tự tin; reason: 1 câu giải thích ngắn gọn căn cứ xác định các nội dung trên",
]


def build_map_system_prompt(shortlist: list[CurriculumUnit]) -> str:
    """Dựng System Prompt cố định (instructions + shortlist node) để tối ưu hóa Prompt Caching."""
    lines = list(_MAP_HEADER_LINES)
    if shortlist:
        lines.append(f"\nDANH SÁCH NODE:\n{build_node_listing(shortlist)}")
    example = (
        '[{"topic": "...", "nodes": [{"node_id": 1, "weight": 0.6}, {"node_id": 2, "weight": 0.4}], '
        '"bloom_level": 4, "off_curriculum_weight": 0.0, "excerpt": "...", "confidence": 0.9, "reason": "..."}]'
    )
    return "\n".join(lines) + f"\n\nCHỈ trả về 1 JSON array, không giải thích, không markdown:\n{example}"


def build_map_prompt(text: str, shortlist: list[CurriculumUnit]) -> str:
    """Dựng prompt chuỗi đơn (dành cho fallback / kiểm thử)."""
    return build_map_system_prompt(shortlist) + f"\n\nNội dung đề:\n{text}"


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


def _invoke_map(
    model: Any,
    text: str,
    shortlist: list[CurriculumUnit],
    system_override: str | None = None,
) -> str:
    """Gọi LLM 1 lần với cấu trúc [SystemMessage, HumanMessage] tối ưu Prompt Caching (DeepSeek/OpenAI).

    Phần SystemMessage (instructions + danh sách node) cố định cho cùng môn/khối → DeepSeek tự động hit
    Context Cache (giảm 90% chi phí và giảm 80% latency).
    """
    system_content = system_override or build_map_system_prompt(shortlist)
    user_content = f"Nội dung đề/câu hỏi cần phân tích:\n{text[:8000]}"
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=user_content),
    ]

    try:
        if hasattr(model, "bind") and not hasattr(model, "_mock_return_value"):
            invoker = model.bind(temperature=0.0)
            response = invoker.invoke(messages)
        else:
            response = model.invoke(messages)
    except Exception:
        try:
            # Fallback 1: gọi không bind
            response = model.invoke(messages)
        except Exception:
            try:
                # Fallback 2: gọi dạng string đơn nếu model là wrapper cũ
                fallback_prompt = f"{system_content}\n\n{user_content}"
                response = model.invoke(fallback_prompt)
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
    rejudge_system = (
        "Bạn là chuyên gia khảo thí. Các ý dưới đây bị đánh giá 'ngoài chương trình' (không khớp node nào trong danh sách). "
        "Xem lại THẬT KỸ dưới lăng kính của Khung chương trình học được cung cấp:\n"
        "- Nếu ý thực chất thuộc node nào đó (dù diễn đạt khác / đổi ngữ cảnh đời thực) thì map lại đúng format JSON array như trước.\n"
        "- Nếu thật sự ngoài chương trình thì giữ nodes = [] và off_curriculum_weight = 1.0.\n\n"
        f"DANH SÁCH NODE:\n{build_node_listing(shortlist)}"
    )
    rejudge_user = "Các ý cần xem lại:\n" + "\n".join(
        f"- {item.topic}: {item.excerpt or ''} ({item.reason or 'không có lý do'})" for item in nulls
    )
    second = parse_mapped_items(_invoke_map(model, rejudge_user, shortlist, system_override=rejudge_system), valid_ids)
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
        if not item.nodes:
            resolved.append(
                ResolvedCompetency(
                    topic=item.topic,
                    excerpt=item.excerpt,
                    bloom_level=item.bloom_level,
                    weight=item.off_curriculum_weight or 1.0,
                    unit_id=None,
                    unit_code=None,
                    unit_name="Ngoài chương trình",
                    matched_catalog=False,
                    off_curriculum=True,
                    off_curriculum_weight=item.off_curriculum_weight or 1.0,
                    chapter=None,
                    lesson=None,
                    candidates=item.candidates,
                    confidence=item.confidence,
                    reason=item.reason,
                )
            )
            continue
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
                    confidence=item.confidence,
                    reason=item.reason,
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


def _split_even_preserving_total(weight: float, n: int) -> list[float]:
    """Chia đều `weight` cho `n` phần, bảo toàn tổng (largest-remainder, 3 chữ số thập phân).

    VD chiếc 0.40/3 → [0.133, 0.133, 0.134] (tổng đúng 0.400) để khớp NUMERIC(5,3).
    """
    if n <= 0:
        return []
    base = round(weight / n, 3)
    parts = [base] * n
    diff = round(weight - base * n, 3)  # phần dư sau khi cắt đều (có thể âm/dương)
    for i in range(n):
        if abs(diff) < 1e-9:
            break
        step = 0.001 if diff > 0 else -0.001
        parts[i] = round(parts[i] + step, 3)
        diff = round(diff - step, 3)
    return parts


def roll_chapter_to_lessons(
    merged: dict[int, tuple[int, float]],
    catalog_by_id: dict[int, Any],
) -> dict[int, tuple[int, float]]:
    """Khi ma trận đề map vào CHƯƠNG, tách xuống các bài con (chia đều weight).

    `merged`: {unit_id: (bloom, weight)} từ merge_by_unit.
    `catalog_by_id`: {unit_id: CurriculumUnit} của shortlist (gồm cả chương + bài).
    Node đã là BÀI → giữ nguyên; chương không có bài con trong catalog → giữ chương + log.
    """
    lesson_ids_by_chapter: dict[int, list[int]] = {}
    for uid, unit in catalog_by_id.items():
        if unit.parent_id is not None:
            lesson_ids_by_chapter.setdefault(unit.parent_id, []).append(uid)

    out: dict[int, tuple[int, float]] = {}
    for unit_id, (bloom_level, weight) in merged.items():
        unit = catalog_by_id.get(unit_id)
        is_chapter = unit is not None and unit.parent_id is None
        if not is_chapter:
            out[unit_id] = (bloom_level, weight)
            continue
        children = lesson_ids_by_chapter.get(unit_id, [])
        if not children:
            logger.warning("Chương %s không có bài con trong catalog — giữ nguyên weight.", unit_id)
            out[unit_id] = (bloom_level, weight)
            continue
        parts = _split_even_preserving_total(weight, len(children))
        for lesson_id, part in zip(children, parts, strict=False):
            out[lesson_id] = (bloom_level, part)
    return out


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
            confidence=item.confidence,
            reason=item.reason,
            image_url=item.image_url,
            has_figure=item.has_figure,
            question_share=item.question_share,
            is_primary=item.is_primary,
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


def _parse_question_score(score_text: str | None) -> float | None:
    """Trích xuất điểm số từ chuỗi điểm ghi trong đề (vd: '(2.0 điểm)', '1,5 đ', '2đ')."""
    if not score_text:
        return None
    cleaned = score_text.replace(",", ".").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        try:
            val = float(match.group(1))
            if 0.1 <= val <= 100.0:
                return val
        except Exception:
            pass
    return None


def classify_segmented_question(
    q: vlm.SegmentedQuestion,
    shortlist: list[CurriculumUnit],
    llm: Any = None,
) -> list[ResolvedCompetency]:
    """Phân loại 1 câu hỏi đơn lẻ (Stage 2) và gán image_url/has_figure."""
    items = map_items(q.text, shortlist, llm)
    if not items:
        return [
            ResolvedCompetency(
                topic=q.text[:80],
                excerpt=q.text,
                bloom_level=2,
                weight=1.0,
                unit_id=None,
                unit_code=None,
                unit_name="Ngoài chương trình",
                matched_catalog=False,
                off_curriculum=True,
                off_curriculum_weight=1.0,
                image_url=q.image_data_url,
                has_figure=q.has_figure,
            )
        ]
    items = rejudge_null_items(items, shortlist, llm)
    resolved = _expand_mapped(items, shortlist)
    resolved, items = _normalize_resolved(resolved, items)
    if not resolved:
        resolved = [
            ResolvedCompetency(
                topic=q.text[:80],
                excerpt=q.text,
                bloom_level=2,
                weight=1.0,
                unit_id=None,
                unit_code=None,
                unit_name="Ngoài chương trình",
                matched_catalog=False,
                off_curriculum=True,
                off_curriculum_weight=1.0,
                image_url=q.image_data_url,
                has_figure=q.has_figure,
                question_share=1.0,
                is_primary=True,
            )
        ]
    else:
        resolved.sort(key=lambda r: r.weight, reverse=True)
        tot_q_w = sum(r.weight for r in resolved) or 1.0
        for idx, r in enumerate(resolved):
            r.excerpt = q.text
            r.image_url = q.image_data_url
            r.has_figure = q.has_figure
            share = round(r.weight / tot_q_w, 4)
            r.question_share = share
            r.is_primary = (idx == 0 or share >= 0.5)
    return resolved


def analyze_exam_paper(exam_paper_id: int) -> None:
    """Phân tích nội dung 1 đề thi (2-Stage Hierarchical Pipeline: Segment -> Parallel Classify -> Aggregate)."""
    db = SessionLocal()
    t_start = time.monotonic()
    try:
        paper = db.get(ExamPaper, exam_paper_id)
        if paper is None:
            return

        grade_number = _resolve_grade_number(db, paper)
        semester = paper.semester_id if paper.semester_id in (1, 2) else None
        shortlist = build_shortlist(db, paper.subject_id, grade_number, semester)

        file_path = storage.exam_file_path(paper.file_url)

        # Stage 1: Thử bóc tách đề thành các câu hỏi độc lập + tọa độ + cắt ảnh bằng Qwen-VL
        segmented_questions: list[vlm.SegmentedQuestion] = []
        raw_text = ""
        try:
            t0 = time.monotonic()
            segmented_questions = vlm.segment_exam_questions(file_path, paper.file_type)
            logger.info("CDI[%s] Qwen segment: %.2fs (%d câu hỏi)", exam_paper_id, time.monotonic() - t0, len(segmented_questions))
        except Exception as exc:
            logger.warning("CDI[%s] Qwen segment thất bại hoặc chưa cấu hình, fallback OCR text: %s", exam_paper_id, exc)

        resolved: list[ResolvedCompetency] = []

        if segmented_questions:
            raw_text = "\n\n".join(f"Câu {q.question_number}: {q.text}" for q in segmented_questions)

            # Stage 2: Gọi song song classify_segmented_question cho từng câu hỏi
            t0 = time.monotonic()
            max_workers = min(len(segmented_questions), 8)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    pool.submit(classify_segmented_question, q, shortlist)
                    for q in segmented_questions
                ]
                results_per_question = [f.result() for f in futures]
            logger.info("CDI[%s] Stage 2 parallel classify: %.2fs", exam_paper_id, time.monotonic() - t0)

            # Stage 3: Phân bổ trọng số câu hỏi & tổng hợp
            scores = [_parse_question_score(q.score_text) for q in segmented_questions]
            has_scores = all(s is not None for s in scores) and sum(s for s in scores if s is not None) > 0
            if has_scores:
                total_score = sum(s for s in scores if s is not None)
                q_weights = [(s / total_score) if s else 0.0 for s in scores]
            else:
                n_q = len(segmented_questions)
                q_weights = [1.0 / n_q] * n_q if n_q > 0 else []

            for q_idx, q_resolved in enumerate(results_per_question):
                q_weight = q_weights[q_idx] if q_idx < len(q_weights) else (1.0 / len(segmented_questions))
                for r in q_resolved:
                    r.weight = round(r.weight * q_weight, 4)
                    resolved.append(r)

            # Chuẩn hóa lại tổng trọng số về 1.0 nếu cần
            tot_w = sum(r.weight for r in resolved)
            if tot_w > 0:
                for r in resolved:
                    r.weight = round(r.weight / tot_w, 4)

        else:
            # Fallback 1-Pass cũ (khi VLM offline hoặc file không parse được JSON)
            t0 = time.monotonic()
            text = extract_exam_text(file_path, paper.file_type)
            raw_text = text
            logger.info("CDI[%s] Fallback trích text: %.2fs (%d ký tự)", exam_paper_id, time.monotonic() - t0, len(text))
            items = map_items(text, shortlist)
            if items:
                items = rejudge_null_items(items, shortlist)
                resolved = _expand_mapped(items, shortlist)
                resolved, items = _normalize_resolved(resolved, items)

        if not resolved:
            paper.content_analyzed_at = _now()
            paper.content_source = paper.file_type
            db.commit()
            return

        merged = merge_by_unit(resolved)
        merged = roll_chapter_to_lessons(merged, {u.id: u for u in shortlist})
        if merged:
            _persist_competencies(db, paper.id, merged)
        else:
            logger.warning("Đề %s không map được node nào.", paper.id)

        paper.content_difficulty = cdi_from_bloom_mix([(item.bloom_level, item.weight) for item in resolved])
        analysis = build_content_analysis(
            AnalysisBuildInput(items=resolved, catalog=shortlist, cdi=paper.content_difficulty, model=None)
        )
        paper.ai_analysis = {**(paper.ai_analysis or {}), _ANALYSIS_KEY: analysis.model_dump(mode="json"), "raw_text": raw_text}
        paper.content_analyzed_at = _now()
        paper.content_source = paper.file_type
        db.commit()
    except Exception:  # noqa: BLE001 - lỗi nền không được làm crash app
        logger.exception("Lỗi khi phân tích CDI cho đề %s", exam_paper_id)
        db.rollback()
        # Đánh dấu hoàn tất (dù lỗi) để frontend không poll mãi.
        paper = db.get(ExamPaper, exam_paper_id)
        if paper is not None:
            paper.content_analyzed_at = _now()
            paper.content_source = paper.file_type
            paper.ai_analysis = {**(paper.ai_analysis or {}), "error": "LLM analysis failed"}
            db.commit()
    finally:
        logger.info("CDI[%s] tổng thời gian: %.2fs", exam_paper_id, time.monotonic() - t_start)
        db.close()


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
