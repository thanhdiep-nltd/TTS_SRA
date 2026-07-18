"""Sinh câu hỏi DRAFT bằng LLM + RAG cho ngân hàng câu hỏi (AI Exam Generation).

Câu sinh ra LUÔN ở trạng thái DRAFT — phải qua duyệt người (xem api/v1/question_bank.py)
mới được dùng để ráp đề chính thức. RAG grounding (search_textbook) là BẮT BUỘC: không tìm
được nội dung SGK phù hợp thì KHÔNG sinh câu (tránh LLM bịa ngoài chương trình).

Guardrail CỨNG trước khi vào kho = bám nguồn thật (is_grounded) + đáp án MCQ/TRUE_FALSE hợp lệ
(has_valid_mcq_answer) — xem passes_guardrails. Bloom lệch, tự-giải-lại (self-consistency) và
critic CHỈ là cờ mềm ưu tiên rà soát, KHÔNG loại câu và KHÔNG thay người duyệt.
Xem docs/exam_generation_design.md §5.
"""

import difflib
import json
import logging
import math
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import CurriculumUnit, Misconception, QuestionItem, Subject
from src.services import notifications, retrieval
from src.services.llm import get_llm
from src.services.retrieval import (
    rag_mon_slug,  # noqa: F401 — re-export tương thích ngược (dùng chung với content_difficulty)
)

logger = logging.getLogger(__name__)

_MAX_RAG_CONTEXT_CHARS = 4000

_QUESTION_TYPE_LABEL = {
    enums.QuestionType.MCQ: "trắc nghiệm 4 lựa chọn (A-D)",
    enums.QuestionType.TRUE_FALSE: "đúng/sai",
    enums.QuestionType.SHORT_ANSWER: "trả lời ngắn",
    enums.QuestionType.ESSAY: "tự luận",
}

_GENERATE_PROMPT = (
    "Bạn là giáo viên ra đề môn {subject} lớp {grade}. Dựa HOÀN TOÀN vào NỘI DUNG SGK dưới đây "
    '(các đoạn đã đánh nhãn [Nguồn i]), hãy soạn {count} câu hỏi loại "{qtype}" cho chủ đề '
    '"{unit_name}", đúng mức Bloom {bloom} (1=Nhớ, 2=Hiểu, 3=Vận dụng, 4=Phân tích, 5=Đánh giá, 6=Sáng tạo).\n\n'
    "LUẬT BẮT BUỘC:\n"
    '- Mỗi câu tự đủ ngữ cảnh: KHÔNG viết "theo đoạn văn trên", "trong SGK".\n'
    '- Trắc nghiệm: ĐÚNG 4 lựa chọn A, B, C, D; ĐÚNG 1 đáp án đúng; CẤM "Tất cả các đáp án trên" '
    'hoặc "A và B đúng".\n'
    "- MỖI phương án nhiễu phải phản ánh MỘT lỗi tư duy thật của học sinh — ghi lỗi đó vào trường "
    '"misconception" của phương án (đáp án đúng để misconception = null).\n'
    "- grounded_quotes phải TRÍCH NGUYÊN VĂN từ NỘI DUNG SGK ở trên (không tự đặt lại lời).\n"
    "{misconception_block}"
    "\nNỘI DUNG SGK:\n{context}\n\n"
    "Với MỖI câu, trả 1 phần tử JSON đúng dạng:\n"
    '{{"stem": "...", "options": [{{"key":"A","text":"..","misconception":null hoặc "lỗi sai"}}, ...] '
    'hoặc null nếu tự luận, "answer_key": {{"correct":"B"}} (trắc nghiệm) hoặc '
    '{{"answer":"..","rubric":".."}} (tự luận), "solution": "lời giải chi tiết", '
    '"bloom_level": {bloom}, "grounded_quotes": ["..."]}}\n'
    "CHỈ trả về 1 JSON array, KHÔNG markdown, KHÔNG giải thích thêm."
)

_MISCONCEPTION_BLOCK = (
    "- LỖI SAI PHỔ BIẾN của học sinh trường (thống kê từ bài làm) — ƯU TIÊN soạn phương án nhiễu "
    "bám các lỗi này:\n{bullets}\n"
)

_SOLVE_PROMPT = (
    "Hãy giải câu hỏi sau như một học sinh, KHÔNG được xem đáp án có sẵn. Trả về CHỈ 1 JSON: "
    '{{"correct":"<key>"}} (trắc nghiệm) hoặc {{"answer":"<câu trả lời>"}} (tự luận).\n\n'
    "Câu hỏi:\n{stem}\n{options}"
)

_BLOOM_CHECK_PROMPT = (
    "Phân loại mức Bloom của câu hỏi sau theo thang: 1=Nhớ, 2=Hiểu, 3=Vận dụng, 4=Phân tích, "
    '5=Đánh giá, 6=Sáng tạo. Trả về CHỈ 1 JSON: {{"bloom_level": <1-6>}}.\n\nCâu hỏi:\n{stem}\n{options}'
)

_CRITIC_PROMPT = (
    "Bạn là chuyên gia khảo thí. Chấm câu hỏi sau theo rubric, mỗi tiêu chí đạt/không:\n"
    "1. Có ĐÚNG MỘT đáp án đúng không thể tranh cãi.\n"
    "2. Các phương án nhiễu hợp lý (không ngớ ngẩn, không thể bào chữa là đúng).\n"
    "3. Đề bài (stem) rõ ràng, tự đủ ngữ cảnh, không gợi ý đáp án.\n"
    "4. Ngôn ngữ phù hợp học sinh phổ thông.\n"
    'Trả về CHỈ 1 JSON: {{"score": <0-10 tổng thể>, "issues": ["mô tả ngắn từng vấn đề nếu có"]}}.\n\n'
    "Câu hỏi:\n{stem}\n{options}\nĐáp án công bố: {answer}\nLời giải: {solution}"
)


class GeneratedOption(BaseModel):
    key: str
    text: str
    misconception: str | None = None


class GeneratedItem(BaseModel):
    stem: str
    options: list[GeneratedOption] | None = None
    answer_key: dict
    solution: str
    bloom_level: int = Field(ge=1, le=6)
    grounded_quotes: list[str] = Field(default_factory=list)


class InsufficientContextError(Exception):
    """RAG không tìm thấy nội dung SGK phù hợp — KHÔNG sinh câu khi thiếu ngữ cảnh."""


# ============================================================
# LOGIC THUẦN (không DB/LLM, test offline được)
# ============================================================


def _select_hits_within_budget(hits: list[dict], max_chars: int) -> list[dict]:
    """Các hit SGK thực sự được đưa vào context sau khi cắt theo max_chars — dùng chung cho
    build_context/build_grounding_context/rag_hit_meta để 3 hàm này KHÔNG lệch nhau về "đã dùng"."""
    selected: list[dict] = []
    total = 0
    for h in hits:
        text = (h.get("text") or "").strip()
        if not text:
            continue
        selected.append(h)
        total += len(text)
        if total >= max_chars:
            break
    return selected


def build_context(hits: list[dict], max_chars: int = _MAX_RAG_CONTEXT_CHARS) -> str:
    """Ghép các đoạn SGK ĐÃ DÙNG (sau cắt max_chars) thành khối ngữ cảnh cho prompt LLM, MỖI đoạn
    gắn nhãn [Nguồn i: chương — mục] để truy vết. CHỈ dùng cho prompt — KHÔNG dùng để kiểm
    grounding (xem build_grounding_context) vì nhãn [Nguồn i] có thể bị LLM trích dẫn ngược."""
    blocks: list[str] = []
    for idx, h in enumerate(_select_hits_within_budget(hits, max_chars), start=1):
        text = (h.get("text") or "").strip()
        label = " — ".join(str(x) for x in (h.get("chuong"), h.get("heading")) if x)
        header = f"[Nguồn {idx}: {label}]" if label else f"[Nguồn {idx}]"
        blocks.append(f"{header}\n{text}")
    return "\n\n".join(blocks)


def build_grounding_context(hits: list[dict], max_chars: int = _MAX_RAG_CONTEXT_CHARS) -> str:
    """Ngữ cảnh THUẦN VĂN BẢN (không nhãn [Nguồn i]) dùng để kiểm chứng is_grounded — chặn LLM
    'trích dẫn' ngược lại chính nhãn nguồn (build_context) để giả mạo qua guardrail bám nguồn."""
    hits_used = _select_hits_within_budget(hits, max_chars)
    return "\n\n".join((h.get("text") or "").strip() for h in hits_used)


def rag_hit_meta(hits: list[dict], max_chars: int = _MAX_RAG_CONTEXT_CHARS) -> list[dict]:
    """Metadata nguồn CỦA CÁC HIT THỰC SỰ ĐƯỢC DÙNG (sau cắt max_chars) — người duyệt truy ngược
    đúng SGK đã dùng, không liệt kê nhầm nguồn đã bị cắt bỏ trước khi tới prompt."""
    hits_used = _select_hits_within_budget(hits, max_chars)
    return [{k: h.get(k) for k in ("chuong", "heading", "source_md", "score")} for h in hits_used]


def build_generate_prompt(
    subject_name: str,
    grade_number: int,
    unit_name: str,
    bloom_level: int,
    question_type: enums.QuestionType,
    count: int,
    context: str,
    misconceptions: list[str],
) -> str:
    """Dựng prompt sinh câu v2: luật distractor (cấm "tất cả đáp án trên"), yêu cầu tiêm nhãn
    misconception vào mỗi phương án nhiễu, và tuỳ chọn tiêm danh sách lỗi sai phổ biến đã biết
    của chủ đề (nếu có) để LLM bám lỗi thật thay vì bịa phương án nhiễu ngẫu nhiên."""
    block = ""
    if misconceptions:
        bullets = "\n".join(f"  + {m}" for m in misconceptions)
        block = _MISCONCEPTION_BLOCK.format(bullets=bullets)
    return _GENERATE_PROMPT.format(
        subject=subject_name,
        grade=grade_number,
        count=count,
        qtype=_QUESTION_TYPE_LABEL[question_type],
        unit_name=unit_name,
        bloom=bloom_level,
        context=context,
        misconception_block=block,
    )


def _strip_code_fence(raw: str) -> str:
    return re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()


def parse_generated_items(raw: str) -> list[GeneratedItem]:
    """Parse JSON array LLM trả về; bỏ qua phần tử lỗi schema (không chặn cả lô vì 1 câu hỏng)."""
    try:
        data = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError:
        logger.warning("LLM trả JSON không hợp lệ khi sinh câu hỏi.", exc_info=True)
        return []
    if not isinstance(data, list):
        return []
    items = []
    for entry in data:
        try:
            items.append(GeneratedItem(**entry))
        except (ValidationError, TypeError):
            logger.warning("Bỏ qua 1 câu sinh lỗi schema: %s", entry)
    return items


_QUOTE_MATCH_THRESHOLD = 0.8


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().lower()


def quote_in_context(quote: str, context: str, threshold: float = _QUOTE_MATCH_THRESHOLD) -> bool:
    """Quote có thực sự nằm trong context không (chuẩn hóa khoảng trắng/hoa-thường, chịu sai khác nhỏ)."""
    q, c = _normalize_for_match(quote), _normalize_for_match(context)
    if not q or not c:
        return False
    if q in c:
        return True
    match = difflib.SequenceMatcher(None, q, c, autojunk=False).find_longest_match(0, len(q), 0, len(c))
    return match.size / len(q) >= threshold


def is_grounded(item: GeneratedItem, context: str) -> bool:
    """Bám nguồn RAG THẬT: ít nhất 1 trích dẫn phải xuất hiện trong context (chống LLM bịa quote)."""
    return any(quote_in_context(q, context) for q in item.grounded_quotes if q.strip())


_MCQ_KEYS = ["A", "B", "C", "D"]


def has_valid_mcq_answer(item: GeneratedItem, question_type: enums.QuestionType) -> bool:
    """MCQ: đúng 4 lựa chọn A-D; TRUE_FALSE: đúng 2; đáp án đúng phải khớp 1 option. Tự luận: bỏ qua."""
    if question_type in (enums.QuestionType.SHORT_ANSWER, enums.QuestionType.ESSAY):
        return True
    if item.options is None:
        return False
    keys = [o.key for o in item.options]
    if len(keys) != len(set(keys)):
        return False
    if question_type == enums.QuestionType.MCQ and sorted(keys) != _MCQ_KEYS:
        return False
    if question_type == enums.QuestionType.TRUE_FALSE and len(keys) != 2:
        return False
    return item.answer_key.get("correct") in keys


def passes_guardrails(item: GeneratedItem, question_type: enums.QuestionType, context: str) -> bool:
    """Guardrail CỨNG trước khi vào kho: phải bám nguồn thật + đáp án hợp lệ. Bloom/critic là cờ mềm."""
    return is_grounded(item, context) and has_valid_mcq_answer(item, question_type)


_DUP_THRESHOLD = 0.92
_OVERGEN_FACTOR = 1.5
_OVERGEN_CAP = 30


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Độ tương đồng cosine giữa 2 vector embedding; trả 0.0 (không lỗi) nếu rỗng/lệch chiều/vector 0."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def find_duplicate(
    embedding: list[float], existing: list[tuple[UUID, list[float]]], threshold: float = _DUP_THRESHOLD
) -> UUID | None:
    """id câu cũ giống nhất nếu cosine >= threshold (nghi trùng lặp) — cờ mềm, không loại."""
    best_id, best_sim = None, threshold
    for item_id, emb in existing:
        sim = cosine_similarity(embedding, emb)
        if sim >= best_sim:
            best_id, best_sim = item_id, sim
    return best_id


def overgen_count(count: int) -> int:
    """Sinh dư ~50% để sau guardrail vẫn đủ `count` câu (trần 30 tránh prompt quá dài)."""
    return min(_OVERGEN_CAP, math.ceil(count * _OVERGEN_FACTOR))


def _options_text(item: GeneratedItem) -> str:
    """Ghép options thành text "A. .." mỗi dòng — dùng chung cho các prompt cần hiển thị lựa chọn."""
    return "\n".join(f"{o.key}. {o.text}" for o in item.options) if item.options else ""


def build_solve_prompt(item: GeneratedItem) -> str:
    return _SOLVE_PROMPT.format(stem=item.stem, options=_options_text(item))


def parse_solve_answer(raw: str) -> dict | None:
    try:
        return json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError:
        return None


def self_consistency_matches(item: GeneratedItem, solved: dict | None) -> bool | None:
    """So đáp án LLM tự giải độc lập với answer_key gốc. None = không xác định được (không chặn câu)."""
    if solved is None or item.options is None:
        return None  # tự luận: câu trả lời tự do, không so trực tiếp được
    return solved.get("correct") == item.answer_key.get("correct")


def consistency_label(matches: bool | None) -> str:
    return {True: "match", False: "mismatch", None: "unknown"}[matches]


def build_bloom_check_prompt(item: GeneratedItem) -> str:
    """Prompt phân loại Bloom ĐỘC LẬP — cố ý không đưa mức Bloom yêu cầu để tránh mớm."""
    return _BLOOM_CHECK_PROMPT.format(stem=item.stem, options=_options_text(item))


def parse_bloom_check(raw: str) -> int | None:
    """Parse kết quả phân loại Bloom độc lập; None nếu JSON hỏng, mức không phải int (bool bị
    loại vì bool là subclass của int trong Python) hoặc nằm ngoài 1-6."""
    data = parse_solve_answer(raw)
    level = data.get("bloom_level") if isinstance(data, dict) else None
    if isinstance(level, bool) or not isinstance(level, int):
        return None
    return level if 1 <= level <= 6 else None


def bloom_check_label(predicted: int | None, requested: int) -> str:
    """So mức Bloom LLM tự nhận diện (không biết mức yêu cầu) với mức đã yêu cầu khi sinh câu."""
    if predicted is None:
        return "unknown"
    return "match" if predicted == requested else "mismatch"


def build_critic_prompt(item: GeneratedItem) -> str:
    """Prompt chấm câu hỏi theo rubric khảo thí (đáp án duy nhất, nhiễu hợp lý, stem rõ ràng...)."""
    answer = item.answer_key.get("correct") or item.answer_key.get("answer") or "?"
    return _CRITIC_PROMPT.format(stem=item.stem, options=_options_text(item), answer=answer, solution=item.solution)


def parse_critic_result(raw: str) -> dict | None:
    """Parse kết quả critic; None nếu JSON hỏng, score không phải số (bool bị loại vì bool là
    subclass của int trong Python) hoặc nằm ngoài [0, 10]."""
    data = parse_solve_answer(raw)
    if not isinstance(data, dict):
        return None
    score_raw = data.get("score")
    if isinstance(score_raw, bool) or not isinstance(score_raw, int | float):
        return None
    score = float(score_raw)
    if not 0 <= score <= 10:
        return None
    issues = [str(i) for i in data.get("issues", []) if str(i).strip()]
    return {"score": score, "issues": issues}


# ============================================================
# TẦNG DB + LLM
# ============================================================


def _try_solve_independently(llm, item: GeneratedItem) -> dict | None:
    """Guardrail phụ (§5.3) — lỗi ở đây KHÔNG được chặn luồng sinh câu chính."""
    try:
        response = llm.invoke(build_solve_prompt(item))
        raw = response.content if isinstance(response.content, str) else str(response.content)
        return parse_solve_answer(raw)
    except Exception:  # noqa: BLE001 - guardrail phụ, lỗi mạng/LLM không được chặn sinh câu
        logger.warning("Guardrail tự giải lại thất bại, bỏ qua tín hiệu.", exc_info=True)
        return None


def _try_classify_bloom(llm, item: GeneratedItem) -> int | None:
    """Cờ mềm — lỗi không được chặn luồng sinh câu."""
    try:
        response = llm.invoke(build_bloom_check_prompt(item))
        raw = response.content if isinstance(response.content, str) else str(response.content)
        return parse_bloom_check(raw)
    except Exception:  # noqa: BLE001 - guardrail phụ
        logger.warning("Guardrail phân loại Bloom thất bại, bỏ qua tín hiệu.", exc_info=True)
        return None


def _try_critique(llm, item: GeneratedItem) -> dict | None:
    """Cờ mềm — lỗi không được chặn luồng sinh câu."""
    try:
        response = llm.invoke(build_critic_prompt(item))
        raw = response.content if isinstance(response.content, str) else str(response.content)
        return parse_critic_result(raw)
    except Exception:  # noqa: BLE001 - guardrail phụ
        logger.warning("Guardrail phản biện (critic) thất bại, bỏ qua tín hiệu.", exc_info=True)
        return None


_POOL_MAX_WORKERS = 5  # trần call LLM song song / 1 lượt sinh (tránh rate limit khi nhiều GV bấm cùng lúc)


def _unit_misconceptions(db: Session, school_id: UUID, unit_id: UUID, limit: int = 5) -> list[str]:
    """Top lỗi sai phổ biến của chủ đề (của trường hoặc dùng chung) để tiêm vào prompt distractor."""
    stmt = (
        select(Misconception)
        .where(
            Misconception.unit_id == unit_id,
            or_(Misconception.school_id == school_id, Misconception.school_id.is_(None)),
        )
        .order_by(Misconception.evidence_count.desc())
        .limit(limit)
    )
    return [m.description for m in db.execute(stmt).scalars().all()]


def _existing_embeddings(db: Session, school_id: UUID, unit_id: UUID) -> list[tuple[UUID, list[float]]]:
    """(id, stem_embedding) các câu cùng ô đã có — để phát hiện câu mới trùng lặp."""
    stmt = select(QuestionItem).where(QuestionItem.school_id == school_id, QuestionItem.unit_id == unit_id)
    out = []
    for qi in db.execute(stmt).scalars().all():
        emb = (qi.provenance or {}).get("stem_embedding")
        if isinstance(emb, list) and emb:
            out.append((qi.id, emb))
    return out


def _try_embed_stem(stem: str) -> list[float] | None:
    """Embedding cho dedup — lỗi sidecar/Qdrant không được chặn sinh câu (cờ mềm)."""
    try:
        return retrieval.embed_query(stem)
    except retrieval.RetrievalUnavailableError:
        logger.warning("Không embed được stem để dedup, bỏ qua tín hiệu.")
        return None


def generate_items(
    db: Session,
    school_id: UUID,
    created_by: UUID,
    subject_id: UUID,
    grade_number: int,
    unit_id: UUID,
    bloom_level: int,
    question_type: enums.QuestionType,
    count: int,
) -> list[QuestionItem]:
    """Sinh tối đa `count` câu DRAFT cho 1 ô (môn, khối, chuẩn CT, Bloom, loại câu).

    Pipeline: RAG (bắt buộc có ngữ cảnh) -> LLM sinh dư ~50% -> guardrail CỨNG (bám nguồn đã kiểm
    chứng qua grounding_context KHÔNG NHÃN + đáp án hợp lệ) -> lấy `count` câu đầu -> 3 tín hiệu
    MỀM song song (tự giải lại, Bloom độc lập, critic) + dedup embedding -> lưu DRAFT kèm
    provenance đầy đủ.
    """
    subject = db.get(Subject, subject_id)
    unit = db.get(CurriculumUnit, unit_id)
    if subject is None or unit is None:
        raise ValueError("Môn hoặc chuẩn chương trình không tồn tại")

    t0 = time.monotonic()
    hits = retrieval.search_textbook(unit.name, mon=rag_mon_slug(subject.code), lop=str(grade_number))
    context = build_context(hits)
    if not context:
        raise InsufficientContextError(f"Không tìm thấy nội dung SGK cho chủ đề '{unit.name}'")
    grounding_context = build_grounding_context(hits)
    misconceptions = _unit_misconceptions(db, school_id, unit_id)
    logger.info("ItemGen[%s] tra RAG: %.2fs (%d hits)", unit_id, time.monotonic() - t0, len(hits))

    llm = get_llm()
    t0 = time.monotonic()
    prompt = build_generate_prompt(
        subject.name,
        grade_number,
        unit.name,
        bloom_level,
        question_type,
        overgen_count(count),
        context,
        misconceptions,
    )
    response = llm.invoke(prompt)
    raw = response.content if isinstance(response.content, str) else str(response.content)
    candidates = parse_generated_items(raw)
    logger.info("ItemGen[%s] sinh câu: %.2fs (%d candidate)", unit_id, time.monotonic() - t0, len(candidates))

    passing = [it for it in candidates if passes_guardrails(it, question_type, grounding_context)][:count]
    if len(passing) < min(count, len(candidates)):
        logger.info("ItemGen[%s] còn %d/%d câu sau guardrail cứng.", unit_id, len(passing), len(candidates))

    # 3 tín hiệu mềm / câu (tự giải lại + Bloom độc lập + critic) — chạy song song, trần 5 worker.
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=min(_POOL_MAX_WORKERS, max(1, len(passing) * 3))) as pool:
        solve_f = [pool.submit(_try_solve_independently, llm, it) for it in passing]
        bloom_f = [pool.submit(_try_classify_bloom, llm, it) for it in passing]
        critic_f = [pool.submit(_try_critique, llm, it) for it in passing]
        solved = [f.result() for f in solve_f]
        blooms = [f.result() for f in bloom_f]
        critics = [f.result() for f in critic_f]
    logger.info("ItemGen[%s] tín hiệu mềm (song song): %.2fs (%d câu)", unit_id, time.monotonic() - t0, len(passing))

    existing = _existing_embeddings(db, school_id, unit_id)
    created: list[QuestionItem] = []
    for item, sv, bl, cr in zip(passing, solved, blooms, critics, strict=True):
        embedding = _try_embed_stem(item.stem)
        dup_of = find_duplicate(embedding, existing) if embedding else None
        db_item = QuestionItem(
            school_id=school_id,
            subject_id=subject_id,
            grade_number=grade_number,
            unit_id=unit_id,
            bloom_level=item.bloom_level,
            question_type=question_type,
            stem=item.stem,
            options=[o.model_dump() for o in item.options] if item.options else None,
            answer_key=item.answer_key,
            solution=item.solution,
            status=enums.ItemStatus.DRAFT,
            source=enums.ItemSource.AI_GENERATED,
            provenance={
                "model": getattr(llm, "model", None) or getattr(llm, "model_name", None),
                "rag_sources": item.grounded_quotes,
                "rag_hits": rag_hit_meta(hits),
                "self_consistency": consistency_label(self_consistency_matches(item, sv)),
                "bloom_check": bloom_check_label(bl, bloom_level),
                "critic": cr,
                "duplicate_of": str(dup_of) if dup_of else None,
                "stem_embedding": embedding,
            },
            created_by=created_by,
        )
        db.add(db_item)
        db.flush()  # lấy id thật (server_default qua RETURNING) trước khi dùng cho dedup trong lô
        if embedding:
            existing.append((db_item.id, embedding))
        created.append(db_item)
    db.commit()
    for obj in created:
        db.refresh(obj)
    return created


def generate_items_background(
    school_id: UUID,
    created_by: UUID,
    subject_id: UUID,
    grade_number: int,
    unit_id: UUID,
    bloom_level: int,
    question_type: enums.QuestionType,
    count: int,
) -> None:
    """Wrapper chạy qua FastAPI BackgroundTasks — tự mở/đóng session, KHÔNG raise; thất bại thì BÁO."""
    db = SessionLocal()
    try:
        created = generate_items(
            db, school_id, created_by, subject_id, grade_number, unit_id, bloom_level, question_type, count
        )
        if created:
            notifications.notify_question_submitted_batch(db, created)
    except (ValueError, InsufficientContextError, retrieval.RetrievalUnavailableError) as exc:
        logger.warning("Sinh câu hỏi thất bại cho unit=%s bloom=%s.", unit_id, bloom_level, exc_info=True)
        db.rollback()
        _notify_failure_safe(db, school_id, created_by, subject_id, grade_number, str(exc))
    except Exception:  # noqa: BLE001 - lỗi nền không được làm crash app
        logger.exception("Lỗi không mong đợi khi sinh câu hỏi (unit=%s).", unit_id)
        db.rollback()
        _notify_failure_safe(db, school_id, created_by, subject_id, grade_number, "Lỗi hệ thống không mong đợi")
    finally:
        db.close()


def _notify_failure_safe(
    db: Session, school_id: UUID, recipient_id: UUID, subject_id: UUID, grade_number: int, reason: str
) -> None:
    """Gửi thông báo thất bại — bản thân việc báo lỗi cũng không được raise."""
    try:
        notifications.notify_generation_failed(db, school_id, recipient_id, subject_id, grade_number, reason)
    except Exception:  # noqa: BLE001
        logger.exception("Không gửi được thông báo sinh câu thất bại.")
