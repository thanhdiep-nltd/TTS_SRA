import json
import re
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.db.session import SessionLocal
from src.observability import logger
from src.services.llm import get_llm
from src.services.metadata_indexer import get_embedding


class DynamicEntityContext(BaseModel):
    school_years: list[dict] = Field(default_factory=list)
    homeroom_classes: list[dict] = Field(default_factory=list)
    subjects: list[dict] = Field(default_factory=list)
    exams: list[dict] = Field(default_factory=list)
    assignments: list[dict] = Field(default_factory=list)
    students: list[dict] = Field(default_factory=list)
    teachers: list[dict] = Field(default_factory=list)
    exams_moet: list[dict] = Field(default_factory=list)
    grade_scales: list[dict] = Field(default_factory=list)
    formatted_prompt_context: str = ""


class ExtractedEntitySlots(BaseModel):
    subject_keywords: list[str] = Field(
        default_factory=list, description="Danh sách từ khóa môn học hoặc chương trình (ví dụ: ['Toán', 'Toán Tiếng Anh'])"
    )
    class_keywords: list[str] = Field(
        default_factory=list, description="Danh sách từ khóa lớp học hoặc khối (ví dụ: ['10A1', '10A2', 'Khối 7'])"
    )
    exam_keywords: list[str] = Field(
        default_factory=list, description="Danh sách từ khóa kỳ thi hoặc bài kiểm tra (ví dụ: ['Giữa kỳ 1', 'Progress Check 1'])"
    )
    school_year_keywords: list[str] = Field(
        default_factory=list, description="Danh sách từ khóa năm học hoặc niên khóa (ví dụ: ['2024-2025', '2025-2026'])"
    )
    assignment_keywords: list[str] = Field(
        default_factory=list, description="Danh sách tên bài tập LMS hoặc bài giao"
    )
    student_keywords: list[str] = Field(
        default_factory=list, description="Danh sách tên hoặc mã học sinh (ví dụ: ['Dương Thu Hà', 'HS25091332'])"
    )
    teacher_keywords: list[str] = Field(
        default_factory=list, description="Danh sách tên hoặc mã giáo viên"
    )
    semester_keywords: list[str] = Field(
        default_factory=list, description="Danh sách học kỳ (ví dụ: ['HK1', 'HK2'])"
    )


from langchain_core.messages import HumanMessage, SystemMessage


def extract_entity_slots_llm(user_query: str) -> ExtractedEntitySlots:
    """Trích xuất từ khóa thực thể (Entity Slot Extraction) cô lập dạng mảng danh sách bằng LLM JSON prompt siêu nhẹ (~0.3s)."""
    try:
        llm = get_llm()
        system_prompt = (
            "Bạn là trợ lý trích xuất thực thể (Entity Slot Extractor).\n"
            "Hãy bóc tách các danh sách từ khóa danh từ riêng/tên cụ thể từ yêu cầu người dùng dưới dạng JSON có cấu trúc:\n"
            "{\n"
            '  "subject_keywords": ["từ khóa môn học 1", "từ khóa môn học 2"],\n'
            '  "class_keywords": ["từ khóa lớp/khối 1", "từ khóa lớp/khối 2"],\n'
            '  "exam_keywords": ["từ khóa kỳ thi 1", "từ khóa kỳ thi 2"],\n'
            '  "school_year_keywords": ["từ khóa năm học 1", "từ khóa năm học 2"],\n'
            '  "assignment_keywords": ["tên bài tập LMS 1"],\n'
            '  "student_keywords": ["tên/mã học sinh 1", "tên/mã học sinh 2"],\n'
            '  "teacher_keywords": ["tên/mã giáo viên 1"],\n'
            '  "semester_keywords": ["học kỳ 1", "học kỳ 2"]\n'
            "}\n"
            "Nếu một thực thể có nhiều đối tượng trong câu hỏi (ví dụ: môn Toán và môn Toán Tiếng Anh; năm 2024-2025 và 2025-2026), hãy BẮT BUỘC liệt kê TẤT CẢ các đối tượng đó vào mảng tương ứng.\n"
            "Nếu không có thực thể tương ứng trong câu hỏi, hãy để mảng rỗng [].\n"
            "Tuyệt đối KHÔNG bao gồm các từ rác, từ nối hay từ chỉ mệnh lệnh như 'truy vấn', 'danh sách', 'cho tôi', 'học sinh', 'giáo viên'.\n"
            "Chỉ xuất JSON thuần túy, không kèm markdown."
        )
        prompt_msg = f'Yêu cầu người dùng: "{user_query}"'
        res = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt_msg)])
        content = res.content if hasattr(res, "content") else str(res)
        cleaned_json = re.sub(r"^```json\s*", "", content.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"^```\s*", "", cleaned_json, flags=re.MULTILINE)
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json, flags=re.MULTILINE).strip()
        data = json.loads(cleaned_json)

        # Chuyển đổi linh hoạt nếu LLM trả về string đơn lẻ thay vì list
        normalized_data = {}
        for key, val in data.items():
            if isinstance(val, str):
                normalized_data[key] = [val] if val.strip() else []
            elif isinstance(val, list):
                normalized_data[key] = [str(item).strip() for item in val if item and str(item).strip()]
            else:
                normalized_data[key] = []

        return ExtractedEntitySlots(**normalized_data)
    except Exception as exc:
        logger.warning("entity_slot_extraction_fallback", error=str(exc))
        return ExtractedEntitySlots()


def query_slot_entity(db, so_school_id: int, entity_type: str, slot_keyword: str, subject_id: int | None = None, grade_id: int | None = None) -> dict | None:
    """Query Targeted Hybrid Search với Hard Filter theo Context (Hướng 1) và Graceful Fallback."""
    if not slot_keyword or not slot_keyword.strip():
        return None

    k_str = slot_keyword.strip()
    k_clean = re.sub(r"\s+\d+$", "", k_str).strip()
    k_vector = get_embedding(k_str)
    vector_str = f"[{','.join(map(str, k_vector))}]" if k_vector else None

    # Lớp 1: Hard Filter theo Grade Context (nếu có grade_id)
    if entity_type == "SUBJECT" and grade_id is not None:
        # Bước 1a: Ưu tiên lọc tuyệt đối môn thuộc khối của học sinh/lớp (grade_id = :g_id)
        if vector_str:
            sql_strict = text("""
                SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                       (0.4 * (1 - (embedding <=> CAST(:vector AS vector))) + 0.6 * GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name))) AS hybrid_score
                FROM s360.metadata_index
                WHERE so_school_id = :sid AND entity_type = :etype AND embedding IS NOT NULL
                  AND (extra_metadata::jsonb->>'grade_id')::int = :g_id
                ORDER BY hybrid_score DESC
                LIMIT 1;
            """)
            row = db.execute(sql_strict, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean, "vector": vector_str, "g_id": grade_id}).fetchone()
        else:
            sql_strict = text("""
                SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                       GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name)) AS hybrid_score
                FROM s360.metadata_index
                WHERE so_school_id = :sid AND entity_type = :etype
                  AND (extra_metadata::jsonb->>'grade_id')::int = :g_id
                ORDER BY hybrid_score DESC
                LIMIT 1;
            """)
            row = db.execute(sql_strict, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean, "g_id": grade_id}).fetchone()

        if row and float(row[5]) >= 0.60:
            e_meta = row[4]
            meta_dict = e_meta if isinstance(e_meta, dict) else (json.loads(e_meta) if e_meta else {})
            return {
                "id": int(row[3]),
                "code": str(row[2]),
                "name": str(row[1]),
                "score": float(row[5]),
                "metadata": meta_dict,
            }

        # Bước 1b: Xét môn dùng chung toàn trường không phân khối (grade_id IS NULL)
        if vector_str:
            sql_gen = text("""
                SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                       (0.4 * (1 - (embedding <=> CAST(:vector AS vector))) + 0.6 * GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name))) AS hybrid_score
                FROM s360.metadata_index
                WHERE so_school_id = :sid AND entity_type = :etype AND embedding IS NOT NULL
                  AND (extra_metadata::jsonb->>'grade_id') IS NULL
                ORDER BY hybrid_score DESC
                LIMIT 1;
            """)
            row = db.execute(sql_gen, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean, "vector": vector_str}).fetchone()
        else:
            sql_gen = text("""
                SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                       GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name)) AS hybrid_score
                FROM s360.metadata_index
                WHERE so_school_id = :sid AND entity_type = :etype
                  AND (extra_metadata::jsonb->>'grade_id') IS NULL
                ORDER BY hybrid_score DESC
                LIMIT 1;
            """)
            row = db.execute(sql_gen, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean}).fetchone()

        if row and float(row[5]) >= 0.15:
            e_meta = row[4]
            meta_dict = e_meta if isinstance(e_meta, dict) else (json.loads(e_meta) if e_meta else {})
            return {
                "id": int(row[3]),
                "code": str(row[2]),
                "name": str(row[1]),
                "score": float(row[5]),
                "metadata": meta_dict,
            }

    # Lớp 2: Graceful Fallback Toàn diện (Không giới hạn Hard Filter nếu Lớp 1 không trả về kết quả)
    if vector_str:
        sql_fallback = text("""
            SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                   (0.4 * (1 - (embedding <=> CAST(:vector AS vector))) + 0.6 * GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name))) AS hybrid_score
            FROM s360.metadata_index
            WHERE so_school_id = :sid AND entity_type = :etype AND embedding IS NOT NULL
            ORDER BY hybrid_score DESC
            LIMIT 1;
        """)
        row = db.execute(sql_fallback, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean, "vector": vector_str}).fetchone()
    else:
        sql_fallback = text("""
            SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                   GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name)) AS hybrid_score
            FROM s360.metadata_index
            WHERE so_school_id = :sid AND entity_type = :etype
            ORDER BY hybrid_score DESC
            LIMIT 1;
        """)
        row = db.execute(sql_fallback, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean}).fetchone()

    if row and float(row[5]) >= 0.15:
        e_meta = row[4]
        meta_dict = e_meta if isinstance(e_meta, dict) else (json.loads(e_meta) if e_meta else {})
        return {
            "id": int(row[3]),
            "code": str(row[2]),
            "name": str(row[1]),
            "score": float(row[5]),
            "metadata": meta_dict,
        }
    return None


def query_student_direct(db, so_school_id: int, student_keyword: str) -> list[dict]:
    """Option 3: Query khớp chính xác (Case-Insensitive Exact Match) học sinh theo mã hoặc họ tên trong phạm vi trường học (0đ API Cost, Realtime 100%, ~2ms).
    Trả về danh sách tất cả các học sinh khớp (hỗ trợ nhiều học sinh trùng tên).
    """
    if not student_keyword or not student_keyword.strip():
        return []

    k_str = student_keyword.strip()

    # 1. Khớp chính xác theo Mã Học sinh (HS...)
    if re.match(r"^HS\d+$", k_str, re.IGNORECASE):
        sql = text("""
            SELECT st.student_code, st.student_name, st.homeroom_class_id, st.grade_id, st.so_student_id
            FROM s360.dim_homeroom_class_student st
            JOIN s360.dim_homeroom_class hc ON st.homeroom_class_id = hc.id
            WHERE hc.so_school_id = :sid AND UPPER(st.student_code) = UPPER(:kcode) AND st.is_active = 1
            LIMIT 1;
        """)
        row = db.execute(sql, {"sid": so_school_id, "kcode": k_str}).fetchone()
        if row:
            return [{
                "id": int(row[4]) if row[4] else 0,
                "code": str(row[0]),
                "name": str(row[1]),
                "score": 1.0,
                "metadata": {"class_id": int(row[2]), "grade_id": int(row[3])},
            }]

    # 2. Khớp chính xác 100% Họ tên không phân biệt hoa thường (Case-Insensitive Exact Match)
    # Lấy toàn bộ danh sách học sinh trùng tên trong trường (bỏ LIMIT 1)
    sql = text("""
        SELECT st.student_code, st.student_name, st.homeroom_class_id, st.grade_id, st.so_student_id
        FROM s360.dim_homeroom_class_student st
        JOIN s360.dim_homeroom_class hc ON st.homeroom_class_id = hc.id
        WHERE hc.so_school_id = :sid 
          AND UPPER(TRIM(st.student_name)) = UPPER(TRIM(:kname)) 
          AND st.is_active = 1;
    """)
    rows = db.execute(sql, {"sid": so_school_id, "kname": k_str}).fetchall()
    results = []
    for row in rows:
        results.append({
            "id": int(row[4]) if row[4] else 0,
            "code": str(row[0]),
            "name": str(row[1]),
            "score": 1.0,
            "metadata": {"class_id": int(row[2]), "grade_id": int(row[3])},
        })
    return results


def resolve_entities(user_query: str, so_school_id: int) -> DynamicEntityContext:
    """Enterprise Multi-Entity Resolution hỗ trợ mảng danh sách từ khóa & Option 3 Dynamic Student Linking."""
    if not user_query or not user_query.strip():
        return DynamicEntityContext()

    # 1. Bóc tách danh sách Slot từ khóa bằng LLM
    slots = extract_entity_slots_llm(user_query.strip())
    ctx = DynamicEntityContext()

    with SessionLocal() as db:
        # Step 1: Match danh sách Học sinh (Option 3 Direct pg_trgm query)
        seen_student_codes = set()
        for st_kw in slots.student_keywords:
            res_students = query_student_direct(db, so_school_id, st_kw)
            for res_student in res_students:
                if res_student and res_student["code"] not in seen_student_codes:
                    ctx.students.append(res_student)
                    seen_student_codes.add(res_student["code"])

        # Step 2: Match danh sách Lớp học
        seen_class_ids = set()
        for c_kw in slots.class_keywords:
            res_class = query_slot_entity(db, so_school_id, "CLASS", c_kw)
            if res_class and res_class["id"] not in seen_class_ids:
                ctx.homeroom_classes.append(res_class)
                seen_class_ids.add(res_class["id"])

        # Step 3: Chuỗi Fallback 100% Động xác định target_grade_id từ CSDL
        target_grade_id = None
        if ctx.students and len(ctx.students) > 0:
            target_grade_id = ctx.students[0].get("metadata", {}).get("grade_id")
        if not target_grade_id and ctx.homeroom_classes and len(ctx.homeroom_classes) > 0:
            target_grade_id = ctx.homeroom_classes[0].get("metadata", {}).get("grade_id")

        # Step 4: Match danh sách Môn học (truyền target_grade_id vào Soft Priority!)
        seen_subject_ids = set()
        for s_kw in slots.subject_keywords:
            res = query_slot_entity(db, so_school_id, "SUBJECT", s_kw, grade_id=target_grade_id)
            if res and res["id"] not in seen_subject_ids:
                ctx.subjects.append(res)
                seen_subject_ids.add(res["id"])

        # Match danh sách Năm học
        seen_year_ids = set()
        for y_kw in slots.school_year_keywords:
            res = query_slot_entity(db, so_school_id, "SCHOOL_YEAR", y_kw)
            if res and res["id"] not in seen_year_ids:
                ctx.school_years.append(res)
                seen_year_ids.add(res["id"])

        # Match danh sách Kỳ thi
        seen_exam_ids = set()
        first_subj_id = ctx.subjects[0]["id"] if ctx.subjects else None

        for ex_kw in slots.exam_keywords:
            exam_parts = [ex_kw]
            if slots.subject_keywords:
                exam_parts.append(slots.subject_keywords[0])
            if target_grade_id:
                exam_parts.append(f"Khối {target_grade_id}")
            exam_kw_combined = " ".join(exam_parts)

            res_moet = query_slot_entity(db, so_school_id, "EXAM_MOET", exam_kw_combined, subject_id=first_subj_id, grade_id=target_grade_id)
            if res_moet and res_moet["id"] not in seen_exam_ids:
                ctx.exams_moet.append(res_moet)
                seen_exam_ids.add(res_moet["id"])

            res_exam = query_slot_entity(db, so_school_id, "EXAM", exam_kw_combined, subject_id=first_subj_id, grade_id=target_grade_id)
            if res_exam and res_exam["id"] not in seen_exam_ids:
                ctx.exams.append(res_exam)
                seen_exam_ids.add(res_exam["id"])

        # Match danh sách Bài tập LMS
        seen_assign_ids = set()
        for a_kw in slots.assignment_keywords:
            res = query_slot_entity(db, so_school_id, "ASSIGNMENT", a_kw)
            if res and res["id"] not in seen_assign_ids:
                ctx.assignments.append(res)
                seen_assign_ids.add(res["id"])

    # Format Markdown Context Injection block cho LLM
    prompt_lines = [
        f"=== THÔNG TIN DANH MỤC ĐÃ ĐƯỢC CHUẨN HÓA CHO TRƯỜNG {so_school_id} (EXACT VALUES IN DB) ==="
    ]
    if ctx.school_years:
        sy_ids = [sy["id"] for sy in ctx.school_years]
        prompt_lines.append(f"- Các Năm học chuẩn hóa: school_year_ids = {sy_ids}")
        for sy in ctx.school_years:
            prompt_lines.append(f"  + Năm học: id = {sy['id']} (code = '{sy['code']}', fullname = '{sy['name']}')")

    if ctx.homeroom_classes:
        class_ids = [hc["id"] for hc in ctx.homeroom_classes]
        prompt_lines.append(f"- Các Lớp học chuẩn hóa: homeroom_class_ids = {class_ids}")
        for hc in ctx.homeroom_classes:
            g_id = hc["metadata"].get("grade_id", "")
            prompt_lines.append(f"  + Lớp học: id = {hc['id']} (class_name = '{hc['metadata'].get('class_name', hc['name'])}', grade_id = {g_id})")

    if ctx.subjects:
        subject_ids = [sb["id"] for sb in ctx.subjects]
        prompt_lines.append(f"- Các Môn học chuẩn hóa: subject_ids = {subject_ids}")
        for sb in ctx.subjects:
            prompt_lines.append(f"  + Môn học: id = {sb['id']} (code = '{sb['code']}', name = '{sb['name']}')")

    if ctx.students:
        st_codes = [st["code"] for st in ctx.students]
        prompt_lines.append(f"- Các Học sinh chuẩn hóa: student_codes = {st_codes}")
        for st in ctx.students:
            c_id = st["metadata"].get("class_id", "")
            g_id = st["metadata"].get("grade_id", "")
            prompt_lines.append(f"  + Học sinh: student_code = '{st['code']}' (full_name = '{st['name']}', homeroom_class_id = {c_id}, grade_id = {g_id})")

    if ctx.exams:
        ex_ids = [ex["id"] for ex in ctx.exams]
        prompt_lines.append(f"- Các Kỳ thi LMS chuẩn hóa: so_exam_ids = {ex_ids}")
        for ex in ctx.exams:
            sem = ex["metadata"].get("semester_index", 1)
            prompt_lines.append(f"  + Kỳ thi LMS: id = {ex['id']} (exam_name = '{ex['name']}', moet_semester_index = {sem})")

    if ctx.exams_moet:
        item_ids = [em["id"] for em in ctx.exams_moet]
        prompt_lines.append(f"- Các Đầu điểm MOET chuẩn hóa: gradebook_type_item_ids = {item_ids}")
        for em in ctx.exams_moet:
            prompt_lines.append(f"  + Đầu điểm MOET: id = {em['id']} (fullname = '{em['name']}')")

    prompt_lines.append("=============================================================================")
    ctx.formatted_prompt_context = "\n".join(prompt_lines) if len(prompt_lines) > 2 else ""

    logger.info("entity_linker_resolved", so_school_id=so_school_id, subjects_count=len(ctx.subjects), students_count=len(ctx.students), target_grade_id=target_grade_id)
    return ctx
