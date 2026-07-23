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
    school_year: dict | None = None
    homeroom_class: dict | None = None
    subject: dict | None = None
    exam: dict | None = None
    assignment: dict | None = None
    student: dict | None = None
    teacher: dict | None = None
    exam_moet: dict | None = None
    grade_scale: dict | None = None
    formatted_prompt_context: str = ""


class ExtractedEntitySlots(BaseModel):
    subject_keyword: Optional[str] = Field(
        default=None, description="Từ khóa môn học hoặc chương trình (ví dụ: 'Toán', 'Lập trình', 'STEM', 'Cambridge')"
    )
    class_keyword: Optional[str] = Field(
        default=None, description="Từ khóa lớp học hoặc khối (ví dụ: '7A1', '7 - Chuyên Tin', 'Khối 7', '10A1')"
    )
    exam_keyword: Optional[str] = Field(
        default=None, description="Từ khóa kỳ thi hoặc bài kiểm tra (ví dụ: 'giữa kỳ 1', 'Progress Check 1')"
    )
    school_year_keyword: Optional[str] = Field(
        default=None, description="Năm học hoặc niên khóa (ví dụ: '2025-2026', '2025')"
    )
    assignment_keyword: Optional[str] = Field(
        default=None, description="Tên bài tập LMS hoặc bài giao (ví dụ: 'bài tập tuần 3')"
    )
    student_keyword: Optional[str] = Field(
        default=None, description="Tên hoặc mã học sinh (ví dụ: 'Nguyễn Văn A', 'HS250001')"
    )
    teacher_keyword: Optional[str] = Field(
        default=None, description="Tên hoặc mã giáo viên"
    )
    semester_keyword: Optional[str] = Field(
        default=None, description="Học kỳ (ví dụ: 'HK1', 'Học kỳ 2')"
    )


from langchain_core.messages import HumanMessage, SystemMessage


def extract_entity_slots_llm(user_query: str) -> ExtractedEntitySlots:
    """Trích xuất từ khóa thực thể (Entity Slot Extraction) cô lập bằng LLM JSON prompt siêu nhẹ (~0.3s)."""
    try:
        llm = get_llm()
        system_prompt = (
            "Bạn là trợ lý trích xuất thực thể (Entity Slot Extractor).\n"
            "Hãy bóc tách các từ khóa danh từ riêng/tên cụ thể từ yêu cầu người dùng dưới dạng JSON có cấu trúc:\n"
            "{\n"
            '  "subject_keyword": "từ khóa môn học (ví dụ: Toán, Lập trình, STEM...)",\n'
            '  "class_keyword": "từ khóa lớp học/khối (ví dụ: 7A1, 7 - Chuyên Tin, Khối 7...)",\n'
            '  "exam_keyword": "từ khóa kỳ thi (ví dụ: giữa kỳ 1, Progress Check 1...)",\n'
            '  "school_year_keyword": "từ khóa năm học (ví dụ: 2025-2026, 2025...)",\n'
            '  "assignment_keyword": "tên bài tập LMS (nếu có)",\n'
            '  "student_keyword": "tên/mã học sinh (nếu có)",\n'
            '  "teacher_keyword": "tên giáo viên (nếu có)",\n'
            '  "semester_keyword": "học kỳ (nếu có)"\n'
            "}\n"
            "Nếu không có thực thể tương ứng trong câu hỏi, hãy để giá trị null.\n"
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
        return ExtractedEntitySlots(**data)
    except Exception as exc:
        logger.warning("entity_slot_extraction_fallback", error=str(exc))
        return ExtractedEntitySlots()


def query_slot_entity(db, so_school_id: int, entity_type: str, slot_keyword: str, subject_id: int | None = None) -> dict | None:
    """Query Targeted Hybrid Search (pgvector 0.6 + pg_trgm word_similarity 0.4) cho duy nhất entity_type và keyword đã cô lập."""
    if not slot_keyword or not slot_keyword.strip():
        return None

    k_str = slot_keyword.strip()
    k_clean = re.sub(r"\s+\d+$", "", k_str).strip()
    k_vector = get_embedding(k_str)
    vector_str = f"[{','.join(map(str, k_vector))}]" if k_vector else None

    if vector_str:
        sql = text("""
            SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                   (0.6 * (1 - (embedding <=> CAST(:vector AS vector))) + 0.4 * GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name))) AS hybrid_score
            FROM s360.metadata_index
            WHERE so_school_id = :sid AND entity_type = :etype AND embedding IS NOT NULL
            ORDER BY
                CASE WHEN CAST(:subj_id AS integer) IS NOT NULL AND (extra_metadata::jsonb->>'subject_id') IS NOT NULL AND (extra_metadata::jsonb->>'subject_id')::int != CAST(:subj_id AS integer) THEN 1 ELSE 0 END,
                hybrid_score DESC
            LIMIT 1;
        """)
        row = db.execute(sql, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean, "vector": vector_str, "subj_id": subject_id}).fetchone()
    else:
        sql = text("""
            SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                   GREATEST(word_similarity(entity_name, :keyword), word_similarity(:keyword, entity_name), word_similarity(entity_name, :kclean), word_similarity(:kclean, entity_name)) AS hybrid_score
            FROM s360.metadata_index
            WHERE so_school_id = :sid AND entity_type = :etype
            ORDER BY
                CASE WHEN CAST(:subj_id AS integer) IS NOT NULL AND (extra_metadata::jsonb->>'subject_id') IS NOT NULL AND (extra_metadata::jsonb->>'subject_id')::int != CAST(:subj_id AS integer) THEN 1 ELSE 0 END,
                hybrid_score DESC
            LIMIT 1;
        """)
        row = db.execute(sql, {"sid": so_school_id, "etype": entity_type, "keyword": k_str, "kclean": k_clean, "subj_id": subject_id}).fetchone()

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


def resolve_entities(user_query: str, so_school_id: int) -> DynamicEntityContext:
    """Dynamic Entity Resolution via Enterprise LLM Structured Slot Extraction & Targeted Hybrid Search."""
    if not user_query or not user_query.strip():
        return DynamicEntityContext()

    # 1. Bóc tách Slot từ khóa bằng LLM (Enterprise Level)
    slots = extract_entity_slots_llm(user_query.strip())
    matched_by_type: dict[str, dict] = {}

    with SessionLocal() as db:
        # 2. Match Targeted Hybrid Search cho từng slot cô lập
        subj_id = None
        if slots.subject_keyword:
            res = query_slot_entity(db, so_school_id, "SUBJECT", slots.subject_keyword)
            if res:
                matched_by_type["SUBJECT"] = res
                subj_id = res["id"]

        grade_id = None
        if slots.class_keyword:
            res_class = query_slot_entity(db, so_school_id, "CLASS", slots.class_keyword)
            if res_class:
                matched_by_type["CLASS"] = res_class
                grade_id = res_class["metadata"].get("grade_id")

        if slots.school_year_keyword:
            res = query_slot_entity(db, so_school_id, "SCHOOL_YEAR", slots.school_year_keyword)
            if res:
                matched_by_type["SCHOOL_YEAR"] = res

        if slots.exam_keyword:
            exam_parts = [slots.exam_keyword]
            if slots.subject_keyword:
                exam_parts.append(slots.subject_keyword)
            if grade_id:
                exam_parts.append(f"Khối {grade_id}")
            exam_kw = " ".join(exam_parts)

            res_moet = query_slot_entity(db, so_school_id, "EXAM_MOET", exam_kw, subject_id=subj_id)
            if res_moet:
                matched_by_type["EXAM_MOET"] = res_moet
            res_exam = query_slot_entity(db, so_school_id, "EXAM", exam_kw, subject_id=subj_id)
            if res_exam:
                matched_by_type["EXAM"] = res_exam

        if slots.assignment_keyword:
            res = query_slot_entity(db, so_school_id, "ASSIGNMENT", slots.assignment_keyword)
            if res:
                matched_by_type["ASSIGNMENT"] = res

        if slots.student_keyword:
            res = query_slot_entity(db, so_school_id, "STUDENT", slots.student_keyword)
            if res:
                matched_by_type["STUDENT"] = res

        if slots.teacher_keyword:
            res = query_slot_entity(db, so_school_id, "TEACHER", slots.teacher_keyword)
            if res:
                matched_by_type["TEACHER"] = res

        # Fallback chung nếu không bóc được slot nào (query quá ngắn hoặc đơn giản)
        if not matched_by_type:
            q_vector = get_embedding(user_query)
            vector_str = f"[{','.join(map(str, q_vector))}]" if q_vector else None
            if vector_str:
                sql = text("""
                    SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                           (0.6 * (1 - (embedding <=> CAST(:vector AS vector))) + 0.4 * word_similarity(entity_name, :query)) AS hybrid_score
                    FROM s360.metadata_index
                    WHERE so_school_id = :sid AND embedding IS NOT NULL
                    ORDER BY hybrid_score DESC
                    LIMIT 10;
                """)
                rows = db.execute(sql, {"sid": so_school_id, "query": user_query, "vector": vector_str}).fetchall()
            else:
                sql = text("""
                    SELECT entity_type, entity_name, exact_code, exact_id, extra_metadata,
                           word_similarity(entity_name, :query) AS hybrid_score
                    FROM s360.metadata_index
                    WHERE so_school_id = :sid
                    ORDER BY hybrid_score DESC
                    LIMIT 10;
                """)
                rows = db.execute(sql, {"sid": so_school_id, "query": user_query}).fetchall()

            for r in rows:
                e_type, e_name, e_code, e_id, e_meta, score = r[0], r[1], r[2], r[3], r[4], float(r[5])
                if score >= 0.15 and e_type not in matched_by_type:
                    meta_dict = e_meta if isinstance(e_meta, dict) else (json.loads(e_meta) if e_meta else {})
                    matched_by_type[e_type] = {
                        "id": int(e_id),
                        "code": str(e_code),
                        "name": str(e_name),
                        "score": score,
                        "metadata": meta_dict,
                    }

    ctx = DynamicEntityContext(
        school_year=matched_by_type.get("SCHOOL_YEAR"),
        homeroom_class=matched_by_type.get("CLASS"),
        subject=matched_by_type.get("SUBJECT"),
        exam=matched_by_type.get("EXAM"),
        assignment=matched_by_type.get("ASSIGNMENT"),
        student=matched_by_type.get("STUDENT"),
        teacher=matched_by_type.get("TEACHER"),
        exam_moet=matched_by_type.get("EXAM_MOET"),
        grade_scale=matched_by_type.get("GRADE_SCALE"),
    )

    # Format Markdown Context Injection block
    prompt_lines = [
        f"=== THÔNG TIN DANH MỤC ĐÃ ĐƯỢC CHUẨN HÓA CHO TRƯỜNG {so_school_id} (EXACT VALUES IN DB) ==="
    ]
    if ctx.school_year:
        sy = ctx.school_year
        prompt_lines.append(f"- Năm học: school_year_id = {sy['id']} (code = '{sy['code']}', fullname = '{sy['name']}')")
    if ctx.homeroom_class:
        hc = ctx.homeroom_class
        g_id = hc["metadata"].get("grade_id", "")
        prompt_lines.append(f"- Lớp học: homeroom_class_id = {hc['id']} (class_name = '{hc['metadata'].get('class_name', hc['name'])}', grade_id = {g_id})")
    if ctx.subject:
        sb = ctx.subject
        prompt_lines.append(f"- Môn học: subject_id = {sb['id']} (code = '{sb['code']}', name = '{sb['metadata'].get('subject_name', sb['name'])}')")
    if ctx.exam:
        ex = ctx.exam
        sem = ex["metadata"].get("semester_index", 1)
        prompt_lines.append(f"- Kỳ thi LMS: so_exam_id = {ex['id']} (exam_name = '{ex['metadata'].get('exam_name', ex['name'])}', moet_semester_index = {sem})")
    if ctx.exam_moet:
        em = ctx.exam_moet
        prompt_lines.append(f"- Đầu điểm MOET: gradebook_type_item_id = {em['id']} (fullname = '{em['name']}')")
    if ctx.assignment:
        ag = ctx.assignment
        prompt_lines.append(f"- Bài tập LMS: assignment_id = {ag['id']} (fullname = '{ag['metadata'].get('fullname', ag['name'])}')")
    if ctx.student:
        st = ctx.student
        prompt_lines.append(f"- Học sinh: student_code = '{st['code']}' (full_name = '{st['name']}', user_id = {st['id']})")
    if ctx.teacher:
        tc = ctx.teacher
        prompt_lines.append(f"- Giáo viên: teacher_code = '{tc['code']}' (full_name = '{tc['name']}', user_id = {tc['id']})")
    if ctx.grade_scale:
        gs = ctx.grade_scale
        prompt_lines.append(f"- Thang điểm/Học lực: scale_name = '{gs['code']}' (label = '{gs['name']}')")

    prompt_lines.append("=============================================================================")
    ctx.formatted_prompt_context = "\n".join(prompt_lines) if len(prompt_lines) > 2 else ""

    logger.info("entity_linker_resolved", so_school_id=so_school_id, matches=list(matched_by_type.keys()))
    return ctx
