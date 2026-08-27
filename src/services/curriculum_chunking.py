"""Service xử lý Chunking và Vector Search cho Sách Giáo Khoa (PostgreSQL + pgvector).

Chiến lược Chunking theo Cấu trúc Đề mục (Heading/Section-Aware):
1. Đọc text từng trang theo [start_page, end_page] của từng bài học trong CurriculumUnit.
2. Tự động nhận diện cấu trúc đề mục SGK Việt Nam (I, II, 1, 2, Hoạt động, Thực hành...).
3. Gắn context_path: [Tên sách] > [Tên chương] > [Tên bài] > [Đề mục].
4. Nhúng vector embedding (batch) và lưu vào bảng public.curriculum_chunks.
5. Cung cấp hàm search_curriculum_chunks() với pgvector cosine distance để phục vụ Hybrid Evidence Classifier.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import fitz  # PyMuPDF
import httpx
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.models.tables import CurriculumBook, CurriculumChunk, CurriculumUnit
from src.observability import logger
from src.services import vlm

# Các mẫu Heading chuẩn trong SGK Việt Nam
HEADING_PATTERNS = [
    r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.?\s+[^\n]+",          # I. II. III.
    r"^(?:1|2|3|4|5|6|7|8|9|10)\.\s+[^\n]+",                      # 1. 2. 3.
    r"^[A-Z]\.\s+[^\n]+",                                        # A. B. C.
    r"^\d+\.\d+\s+[^\n]+",                                       # 1.1, 1.2
    r"^Hoạt động(?:\s+khám phá|\s+trải nghiệm|\s+\d+)?[^\n]*",    # Hoạt động khám phá
    r"^Thực hành(?:\s+\d+)?[^\n]*",                              # Thực hành
    r"^Vận dụng(?:\s+\d+)?[^\n]*",                               # Vận dụng
    r"^Luyện tập(?:\s+\d+)?[^\n]*",                              # Luyện tập
    r"^Câu hỏi(?:\s+và\s+bài tập|\s+ôn tập)?[^\n]*",             # Câu hỏi ôn tập
    r"^Kiến thức trọng tâm[^\n]*",
    r"^Em có biết[^\n]*",
]
_COMPILED_HEADING_RES = [re.compile(p, re.IGNORECASE) for p in HEADING_PATTERNS]


def is_heading_line(line: str) -> bool:
    """Kiểm tra xem 1 dòng có phải là tiêu đề mục SGK hay không."""
    clean = line.strip()
    if not clean or len(clean) > 150:
        return False
    return any(r.match(clean) for r in _COMPILED_HEADING_RES)


def extract_page_text_with_fallback(
    doc: fitz.Document,
    page_idx: int,
    pdf_path: Path | str | None = None,
    settings: Settings | None = None,
) -> str:
    """Đọc text từ 1 trang PDF qua PyMuPDF, nếu trang scan/ảnh (< 50 chars) thì gọi fallback VLM OCR."""
    if page_idx < 0 or page_idx >= doc.page_count:
        return ""
    try:
        page = doc.load_page(page_idx)
        text_content = page.get_text("text").strip()
        if len(text_content) >= 50:
            return text_content
    except Exception as exc:  # noqa: BLE001
        logger.warning("PyMuPDF read page %d error: %s", page_idx, exc)

    # Fallback VLM nếu text quá ngắn hoặc là scan
    if pdf_path is not None:
        try:
            s = settings or get_settings()
            if vlm.is_configured(s):
                prompt = (
                    "Hãy đọc và chép lại toàn bộ văn bản có trong trang sách này một cách chuẩn xác, "
                    "giữ nguyên cấu trúc các đề mục, công thức và đoạn văn."
                )
                vlm_text = vlm.read_pdf_pages_range(Path(pdf_path), start_page=page_idx + 1, end_page=page_idx + 1, prompt=prompt, settings=s)
                if vlm_text and len(vlm_text.strip()) > 30:
                    return vlm_text.strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("VLM OCR fallback for page %d error: %s", page_idx, exc)

    return ""


def chunk_unit_content(
    unit_id: int | None,
    unit_name: str,
    chapter_name: str,
    book_title: str,
    page_texts: dict[int, str],
) -> list[dict[str, Any]]:
    """Cắt nhỏ nội dung của 1 bài học theo đề mục (Heading-Aware Chunking)."""
    raw_sections: list[dict[str, Any]] = []
    current_heading = "Nội dung bài học"
    current_page = min(page_texts.keys()) if page_texts else 1
    current_lines: list[str] = []

    sorted_pages = sorted(page_texts.keys())
    for p_idx in sorted_pages:
        page_str = page_texts[p_idx]
        lines = [ln.strip() for ln in page_str.split("\n") if ln.strip()]
        for line in lines:
            if is_heading_line(line):
                # Lưu section trước đó nếu có text
                if current_lines:
                    sec_text = "\n".join(current_lines).strip()
                    if sec_text:
                        raw_sections.append({
                            "heading": current_heading,
                            "page_number": current_page + 1,  # 1-indexed cho trang in / tham khảo
                            "text": sec_text,
                        })
                    current_lines = []
                current_heading = line
                current_page = p_idx
            else:
                current_lines.append(line)

    # Lưu section cuối cùng
    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            raw_sections.append({
                "heading": current_heading,
                "page_number": current_page + 1,
                "text": sec_text,
            })

    # Nếu không nhận diện được heading nào, gộp toàn bộ thành các đoạn theo trang
    if not raw_sections and page_texts:
        for p_idx in sorted_pages:
            p_text = page_texts[p_idx].strip()
            if p_text:
                raw_sections.append({
                    "heading": "Toàn văn bài học",
                    "page_number": p_idx + 1,
                    "text": p_text,
                })

    # Chuẩn hóa kích thước chunks: gom mục quá nhỏ (< 40 từ), tách mục quá lớn (> 400 từ)
    final_chunks: list[dict[str, Any]] = []
    buffer_heading = ""
    buffer_page = 1
    buffer_text = ""

    for sec in raw_sections:
        h = sec["heading"]
        p = sec["page_number"]
        t = sec["text"]
        words = t.split()

        if len(words) < 40:
            if buffer_text:
                buffer_text += "\n" + t
            else:
                buffer_heading = h
                buffer_page = p
                buffer_text = t
            continue

        if buffer_text:
            final_chunks.append({
                "unit_id": unit_id,
                "page_number": buffer_page,
                "heading": buffer_heading,
                "context_path": f"{book_title} > {chapter_name} > {unit_name} > {buffer_heading}".strip(" >"),
                "chunk_text": buffer_text.strip(),
            })
            buffer_heading = ""
            buffer_text = ""

        # Nếu đoạn vừa vặn (40..400 từ)
        if len(words) <= 400:
            final_chunks.append({
                "unit_id": unit_id,
                "page_number": p,
                "heading": h,
                "context_path": f"{book_title} > {chapter_name} > {unit_name} > {h}".strip(" >"),
                "chunk_text": t.strip(),
            })
        else:
            # Tách thành các đoạn nhỏ hơn với overlap 1 câu
            paragraphs = [p.strip() for p in t.split("\n") if p.strip()]
            cur_chunk_words: list[str] = []
            part_idx = 1
            for para in paragraphs:
                para_words = para.split()
                if len(cur_chunk_words) + len(para_words) > 350 and cur_chunk_words:
                    part_h = f"{h} (Phần {part_idx})"
                    final_chunks.append({
                        "unit_id": unit_id,
                        "page_number": p,
                        "heading": part_h,
                        "context_path": f"{book_title} > {chapter_name} > {unit_name} > {part_h}".strip(" >"),
                        "chunk_text": " ".join(cur_chunk_words).strip(),
                    })
                    part_idx += 1
                    # Overlap 20 từ cuối
                    cur_chunk_words = cur_chunk_words[-20:] + para_words
                else:
                    cur_chunk_words.extend(para_words)

            if cur_chunk_words:
                part_h = f"{h} (Phần {part_idx})" if part_idx > 1 else h
                final_chunks.append({
                    "unit_id": unit_id,
                    "page_number": p,
                    "heading": part_h,
                    "context_path": f"{book_title} > {chapter_name} > {unit_name} > {part_h}".strip(" >"),
                    "chunk_text": " ".join(cur_chunk_words).strip(),
                })

    if buffer_text:
        final_chunks.append({
            "unit_id": unit_id,
            "page_number": buffer_page,
            "heading": buffer_heading,
            "context_path": f"{book_title} > {chapter_name} > {unit_name} > {buffer_heading}".strip(" >"),
            "chunk_text": buffer_text.strip(),
        })

    return final_chunks


def embed_texts(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    """Nhúng danh sách văn bản (batch embedding) hỗ trợ OpenAI, ShopAIKey, Gemini hoặc Service URL."""
    if not texts:
        return []
    s = settings or get_settings()

    # 1. OpenAI / ShopAIKey
    api_key = s.embedding_openai_api_key or s.openai_api_key
    base_url = (s.embedding_url or s.openai_api_base).rstrip("/")

    if s.embedding_provider == "openai" or (api_key and not s.gemini_api_key):
        try:
            resp = httpx.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": s.openai_embed_model,
                    "input": texts,
                    "dimensions": s.embedding_dim,
                },
                timeout=s.retrieval_timeout_s * 2,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return [item["embedding"] for item in data]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Batch OpenAI embeddings failed: %s", exc)

    # 2. Gemini
    if s.embedding_provider == "gemini" or s.gemini_api_key:
        vectors: list[list[float]] = []
        for t in texts:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_embed_model}:embedContent"
                resp = httpx.post(
                    url,
                    params={"key": s.gemini_api_key},
                    json={
                        "model": f"models/{s.gemini_embed_model}",
                        "content": {"parts": [{"text": t}]},
                        "outputDimensionality": s.embedding_dim,
                    },
                    timeout=s.retrieval_timeout_s,
                )
                resp.raise_for_status()
                vectors.append(resp.json()["embedding"]["values"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini embedding item failed: %s", exc)
                vectors.append([0.0] * s.embedding_dim)
        return vectors

    # 3. Local embedding service fallback
    try:
        resp = httpx.post(
            f"{s.embedding_service_url.rstrip('/')}/embed",
            json={"texts": texts},
            timeout=s.retrieval_timeout_s * 2,
        )
        resp.raise_for_status()
        return resp.json()["vectors"]
    except Exception as exc:  # noqa: BLE001
        logger.error("Local embedding fallback failed: %s", exc)
        return [[0.0] * s.embedding_dim for _ in texts]


def index_book_chunks(
    db: Session,
    book_id: int,
    pdf_path: Path | str,
    settings: Settings | None = None,
) -> int:
    """Cắt lát và index toàn bộ chunks của cuốn sách vào PostgreSQL pgvector (Delete & Replace)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    p_path = Path(pdf_path)
    if not p_path.exists():
        logger.warning("Không tìm thấy file PDF để index chunks: %s", p_path)
        return 0

    book = db.execute(select(CurriculumBook).where(CurriculumBook.id == book_id)).scalars().first()
    if not book:
        logger.warning("Không tìm thấy CurriculumBook ID %s", book_id)
        return 0

    # 1. Delete & Replace: Dọn sạch chunks cũ của chính cuốn sách này
    db.execute(delete(CurriculumChunk).where(CurriculumChunk.book_id == book_id))
    db.commit()

    # 2. Đọc danh sách units của cuốn sách
    units = list(
        db.execute(
            select(CurriculumUnit)
            .where(CurriculumUnit.book_id == book_id)
            .order_by(CurriculumUnit.grade_number, CurriculumUnit.code)
        ).scalars().all()
    )
    if not units:
        logger.info("Cuốn sách ID %s chưa có units nào trong DB để chunk", book_id)
        return 0

    # Lập map parent_name cho các bài học
    id_to_unit = {u.id: u for u in units}
    unit_parent_map = {}
    for u in units:
        if u.parent_id and u.parent_id in id_to_unit:
            unit_parent_map[u.id] = id_to_unit[u.parent_id].name
        else:
            unit_parent_map[u.id] = u.name

    # 3. Trích xuất text từng trang của PDF (tối ưu song song và cache)
    doc = fitz.open(p_path)
    all_chunks: list[dict[str, Any]] = []

    try:
        # Tập hợp tất cả các trang cần đọc
        needed_pages: set[int] = set()
        for u in units:
            start_p = u.start_page
            end_p = u.end_page
            if start_p is None or end_p is None:
                continue
            start_p = max(0, min(start_p, doc.page_count - 1))
            end_p = max(start_p, min(end_p, doc.page_count - 1))
            for p_idx in range(start_p, end_p + 1):
                needed_pages.add(p_idx)

        # Đọc trước nhanh bằng PyMuPDF; nếu trang nào rỗng (scan) thì đưa vào danh sách cần VLM
        page_text_cache: dict[int, str] = {}
        scan_pages_needed: list[int] = []

        for p_idx in needed_pages:
            p_text = doc[p_idx].get_text("text").strip()
            if len(p_text) >= 50:
                page_text_cache[p_idx] = p_text
            else:
                scan_pages_needed.append(p_idx)

        # Chạy song song VLM OCR cho các trang scan để tăng tốc độ gấp 6 lần
        if scan_pages_needed:
            s = settings or get_settings()
            prompt = (
                "Hãy đọc và chép lại toàn bộ văn bản có trong trang sách này một cách chuẩn xác, "
                "giữ nguyên cấu trúc các đề mục, công thức và đoạn văn."
            )
            concurrency = min(6, len(scan_pages_needed))

            def _fetch_scan_page(p_idx: int) -> tuple[int, str]:
                try:
                    res = vlm.read_pdf_pages_range(p_path, start_page=p_idx + 1, end_page=p_idx + 1, prompt=prompt, settings=s)
                    return p_idx, res.strip() if res else ""
                except Exception as exc:  # noqa: BLE001
                    logger.warning("VLM OCR fallback failed for page %d: %s", p_idx, exc)
                    return p_idx, ""

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(_fetch_scan_page, p) for p in scan_pages_needed]
                for fut in as_completed(futures):
                    p_idx, text_res = fut.result()
                    page_text_cache[p_idx] = text_res

        # Tạo chunks cho từng unit
        for u in units:
            start_p = u.start_page
            end_p = u.end_page
            if start_p is None or end_p is None:
                continue
            start_p = max(0, min(start_p, doc.page_count - 1))
            end_p = max(start_p, min(end_p, doc.page_count - 1))

            unit_page_texts = {
                p_idx: page_text_cache.get(p_idx, "")
                for p_idx in range(start_p, end_p + 1)
            }

            ch_name = unit_parent_map.get(u.id, book.title)
            chunks = chunk_unit_content(
                unit_id=u.id,
                unit_name=u.name,
                chapter_name=ch_name,
                book_title=book.title,
                page_texts=unit_page_texts,
            )
            all_chunks.extend(chunks)
    finally:
        doc.close()

    if not all_chunks:
        logger.info("Không tạo được chunk nào cho cuốn sách ID %s", book_id)
        return 0

    # 4. Batch Embed & Lưu vào CSDL
    batch_size = 20
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        texts_to_embed = [
            f"{c['context_path']}\n{c['chunk_text']}" for c in batch
        ]
        embeddings = embed_texts(texts_to_embed, settings=settings)

        for chunk_data, emb in zip(batch, embeddings):
            chunk_obj = CurriculumChunk(
                book_id=book_id,
                unit_id=chunk_data["unit_id"],
                page_number=chunk_data["page_number"],
                heading=chunk_data["heading"],
                context_path=chunk_data["context_path"],
                chunk_text=chunk_data["chunk_text"],
                embedding=emb,
            )
            db.add(chunk_obj)
        db.commit()

    logger.info("Đã index thành công %d chunks cho cuốn sách ID %s (%s)", len(all_chunks), book_id, book.title)
    return len(all_chunks)


def search_curriculum_chunks(
    db: Session,
    query: str,
    subject_id: int,
    grade_number: int,
    top_k: int = 3,
    score_floor: float = 0.45,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Truy vấn Vector Search trên pgvector (Cosine Distance) với LEFT JOIN để lấy bằng chứng SGK."""
    if not query.strip():
        return []
    embeddings = embed_texts([query], settings=settings)
    if not embeddings or not embeddings[0]:
        return []
    query_vector = embeddings[0]

    # Kiểm tra vector không toàn số 0
    if not any(query_vector):
        return []

    sql_query = text(
        """
        SELECT c.id, c.unit_id, u.code AS unit_code, u.name AS unit_name,
               c.page_number, c.heading, c.context_path, c.chunk_text,
               1 - (c.embedding <=> CAST(:query_vector AS vector)) AS similarity
        FROM public.curriculum_chunks c
        LEFT JOIN public.curriculum_units u ON c.unit_id = u.id
        JOIN public.curriculum_books b ON c.book_id = b.id
        WHERE b.subject_id = :subject_id
          AND b.grade_number = :grade_number
          AND 1 - (c.embedding <=> CAST(:query_vector AS vector)) >= :score_floor
        ORDER BY c.embedding <=> CAST(:query_vector AS vector) ASC
        LIMIT :top_k;
        """
    )

    try:
        rows = db.execute(
            sql_query,
            {
                "query_vector": str(query_vector),
                "subject_id": subject_id,
                "grade_number": grade_number,
                "score_floor": score_floor,
                "top_k": top_k,
            },
        ).fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r.id,
                "unit_id": r.unit_id,
                "unit_code": r.unit_code,
                "unit_name": r.unit_name,
                "page_number": r.page_number,
                "heading": r.heading,
                "context_path": r.context_path,
                "chunk_text": r.chunk_text,
                "similarity": float(r.similarity),
            })
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("search_curriculum_chunks pgvector failed: %s", exc)
        return []


def format_evidence_for_prompt(hits: list[dict[str, Any]]) -> str:
    """Định dạng kết quả Vector Search thành văn bản Bằng Chứng trực quan cho LLM đối chiếu."""
    if not hits:
        return ""
    lines = ["BẰNG CHỨNG TRÍCH XUẤT TỪ SGK (EVIDENCE ĐỐI CHIẾU):"]
    for idx, h in enumerate(hits, start=1):
        path = h.get("context_path") or f"Bài: {h.get('unit_name', '')}"
        page = h.get("page_number", "")
        txt = h.get("chunk_text", "")
        # Rút gọn text nếu quá dài (~300 ký tự)
        if len(txt) > 350:
            txt = txt[:340].rstrip() + "..."
        lines.append(f"{idx}. 📖 [{path}] (Trang {page}) [Khớp: {h.get('similarity', 0):.2f}]:\n   \"{txt}\"")
    return "\n".join(lines)
