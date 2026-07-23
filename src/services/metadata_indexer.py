import asyncio
import json
from sqlalchemy import text
from src.config import get_settings
from src.db.session import SessionLocal
from src.observability import logger


from functools import lru_cache


@lru_cache(maxsize=4096)
def get_embedding(text_input: str) -> list[float] | None:
    """Sinh vector embedding cho chuỗi văn bản sử dụng Provider đã cấu hình (Gemini REST API hoặc OpenAI / Proxy)."""
    settings = get_settings()
    if not text_input or not text_input.strip():
        return None

    txt = text_input.strip()

    try:
        if settings.embedding_provider in ("openai", "text-embedding-3-large") or settings.embedding_openai_api_key:
            import httpx

            api_key = settings.embedding_openai_api_key or settings.openai_api_key
            api_base = settings.embedding_url or settings.openai_api_base
            if api_base and not api_base.startswith("http"):
                api_base = f"https://{api_base}"
            if api_base and not api_base.endswith("/v1"):
                api_base = f"{api_base.rstrip('/')}/v1"

            url = f"{api_base}/embeddings"
            payload = {
                "model": settings.openai_embed_model,
                "input": txt,
                "dimensions": settings.embedding_dim,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return data["data"][0]["embedding"]
                else:
                    logger.warning("openai_embedding_api_error", status_code=res.status_code, response=res.text)
                    return None

        elif settings.embedding_provider == "gemini" and settings.gemini_api_key:
            import httpx

            model_name = getattr(settings, "gemini_embed_model", "gemini-embedding-2")
            if "text-embedding-004" in model_name:
                model_name = "gemini-embedding-2"

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent?key={settings.gemini_api_key}"
            payload = {
                "model": f"models/{model_name}",
                "content": {"parts": [{"text": txt}]},
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("embedding", {}).get("values")
                else:
                    logger.warning("gemini_embedding_api_error", status_code=res.status_code, response=res.text)
    except Exception as e:
        logger.warning("embedding_generation_failed", error=str(e), text=text_input)
    return None


def sync_school_metadata(so_school_id: int) -> int:
    """Quét dữ liệu danh mục từ DB chính cho trường `so_school_id` và đồng bộ vào `s360.metadata_index`.

    Trả về số lượng bản ghi danh mục đã được đồng bộ.
    """
    settings = get_settings()
    records_to_insert = []

    with SessionLocal() as db:
        # 1. School Years (s360.dim_school_year)
        years = db.execute(text("SELECT id, code, fullname FROM s360.dim_school_year")).fetchall()
        for y in years:
            y_id, code, fullname = y[0], y[1], y[2]
            records_to_insert.append(
                {
                    "so_school_id": so_school_id,
                    "entity_type": "SCHOOL_YEAR",
                    "entity_name": fullname,
                    "exact_code": str(code),
                    "exact_id": int(y_id),
                    "extra_metadata": {"fullname": fullname, "code": str(code)},
                }
            )

        # 2. Homeroom Classes (s360.dim_homeroom_class)
        classes = db.execute(
            text("SELECT id, code, fullname, grade_id FROM s360.dim_homeroom_class WHERE so_school_id = :sid"),
            {"sid": so_school_id},
        ).fetchall()
        for c in classes:
            c_id, c_code, c_name, g_id = c[0], c[1], c[2], c[3]
            records_to_insert.append(
                {
                    "so_school_id": so_school_id,
                    "entity_type": "CLASS",
                    "entity_name": f"Lớp {c_name}",
                    "exact_code": str(c_code),
                    "exact_id": int(c_id),
                    "extra_metadata": {"class_name": c_name, "grade_id": g_id},
                }
            )
            records_to_insert.append(
                {
                    "so_school_id": so_school_id,
                    "entity_type": "CLASS",
                    "entity_name": str(c_name),
                    "exact_code": str(c_code),
                    "exact_id": int(c_id),
                    "extra_metadata": {"class_name": c_name, "grade_id": g_id},
                }
            )

        # 3. Subjects (s360.dim_subject) - Nạp động 100% từ CSDL
        subjects = db.execute(text("SELECT id, code, name FROM s360.dim_subject")).fetchall()
        for s in subjects:
            s_id, s_code, s_name = s[0], s[1], s[2]
            names_to_add = {str(s_name), f"Môn {s_name}", str(s_code)}
            if s_code and "_" in str(s_code):
                base_code = str(s_code).split("_")[0]
                if len(base_code) >= 2:
                    names_to_add.add(base_code)

            for entry_name in names_to_add:
                records_to_insert.append(
                    {
                        "so_school_id": so_school_id,
                        "entity_type": "SUBJECT",
                        "entity_name": entry_name,
                        "exact_code": str(s_code),
                        "exact_id": int(s_id),
                        "extra_metadata": {"subject_name": s_name},
                    }
                )

        # 4. Exams (s360.dim_exam)
        exams = db.execute(
            text(
                "SELECT e.id, e.exam_code, e.exam_name, e.moet_semester_index FROM s360.dim_exam e WHERE e.id IN (SELECT so_exam_id FROM s360.fact_gradebooks WHERE so_school_id = :sid)"
            ),
            {"sid": so_school_id},
        ).fetchall()
        for e in exams:
            e_id, e_code, e_name, sem = e[0], e[1], e[2], e[3]
            records_to_insert.append(
                {
                    "so_school_id": so_school_id,
                    "entity_type": "EXAM",
                    "entity_name": str(e_name),
                    "exact_code": str(e_code) if e_code else str(e_id),
                    "exact_id": int(e_id),
                    "extra_metadata": {"exam_name": e_name, "semester_index": sem},
                }
            )

        # 5. Assignments (s360.dim_so_assignment)
        assignments = db.execute(
            text("SELECT assignment_id, code, fullname FROM s360.dim_so_assignment WHERE so_school_id = :sid ORDER BY assignment_id LIMIT 50"),
            {"sid": so_school_id},
        ).fetchall()
        for a in assignments:
            a_id, a_code, a_fullname = a[0], a[1], a[2]
            records_to_insert.append(
                {
                    "so_school_id": so_school_id,
                    "entity_type": "ASSIGNMENT",
                    "entity_name": str(a_fullname),
                    "exact_code": str(a_code) if a_code else str(a_id),
                    "exact_id": int(a_id),
                    "extra_metadata": {"fullname": a_fullname},
                }
            )

        # 6. MOET Exam Items (s360.dim_exam_moet)
        moet_exams = db.execute(
            text("SELECT gradebook_type_item_id, gradebook_type_items_fullname, moet_semester_index FROM s360.dim_exam_moet")
        ).fetchall()
        for m in moet_exams:
            m_id, m_name, sem = m[0], m[1], m[2]
            em_subj_id = None
            for s in subjects:
                if s[2] and str(s[2]).lower() in str(m_name).lower():
                    em_subj_id = int(s[0])
                    break
            records_to_insert.append(
                {
                    "so_school_id": so_school_id,
                    "entity_type": "EXAM_MOET",
                    "entity_name": str(m_name),
                    "exact_code": str(m_id),
                    "exact_id": int(m_id),
                    "extra_metadata": {"fullname": m_name, "semester_index": sem, "subject_id": em_subj_id},
                }
            )

        # 7. Grade Scale Details (s360.dim_grade_scale_detail)
        scales = db.execute(
            text("SELECT id, scale_name, grade_letter, grade_label FROM s360.dim_grade_scale_detail")
        ).fetchall()
        for s in scales:
            s_id, sc_name, g_letter, g_label = s[0], s[1], s[2], s[3]
            if g_label:
                records_to_insert.append(
                    {
                        "so_school_id": so_school_id,
                        "entity_type": "GRADE_SCALE",
                        "entity_name": str(g_label),
                        "exact_code": str(sc_name),
                        "exact_id": int(s_id),
                        "extra_metadata": {"grade_letter": g_letter, "grade_label": g_label},
                    }
                )

        # Xóa bản ghi cũ của school_id này trước khi chèn lại
        db.execute(
            text("DELETE FROM s360.metadata_index WHERE so_school_id = :sid"),
            {"sid": so_school_id},
        )
        db.commit()

        # Chèn danh mục mới + sinh embedding theo lô song song (Parallel ThreadPool)
        from concurrent.futures import ThreadPoolExecutor

        def fetch_emb(item):
            emb = get_embedding(item["entity_name"])
            return item, f"[{','.join(map(str, emb))}]" if emb else None

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(fetch_emb, records_to_insert))

        count = 0
        for item, emb_str in results:
            db.execute(
                text("""
                    INSERT INTO s360.metadata_index 
                    (so_school_id, entity_type, entity_name, exact_code, exact_id, extra_metadata, embedding)
                    VALUES (:so_school_id, :entity_type, :entity_name, :exact_code, :exact_id, :extra_metadata, CAST(:embedding AS vector))
                """),
                {
                    "so_school_id": item["so_school_id"],
                    "entity_type": item["entity_type"],
                    "entity_name": item["entity_name"],
                    "exact_code": item["exact_code"],
                    "exact_id": item["exact_id"],
                    "extra_metadata": json.dumps(item["extra_metadata"]),
                    "embedding": emb_str,
                },
            )
            count += 1

        db.commit()
        logger.info("metadata_indexer_synced", so_school_id=so_school_id, total_records=count)
        return count
