import sqlglot
import sqlglot.expressions as exp

from src.observability import logger, sql_guardrail_rejections_total

ALLOWED_TABLES = {
    # Metadata / System tables for LLM self-correction
    "columns",
    "tables",
    "metadata_index",

    # Public schema tables
    "schools",
    "users",
    "refresh_tokens",
    "classroom_recordings",
    "audit_logs",
    "ai_sessions",
    "ai_messages",
    "ai_session_attachments",
    "report_schedules",
    "ai_observability_snapshots",
    "ai_evaluations",

    # S360 Dimensions
    "dim_school_year",
    "dim_homeroom_class",
    "dim_homeroom_class_student",
    "dim_subject",
    "dim_exam",
    "dim_exam_moet",
    "dim_so_assignment",
    "dim_grade_scale",
    "dim_grade_scale_detail",
    "dim_behavior",
    "dim_course",

    # S360 Facts
    "fact_gradebooks",
    "fact_gradebooks_moet",
    "fact_so_assignment_grade",
    "fact_subject_academic_records",
    "fact_overall_academic_records",
    "fact_course_enrolls",
    "fact_so_evaluate_process_subjects",
    "fact_behavior_logs",
    "fact_so_homeroom_class_late_attendances",
    "fact_absent_logs",
    "fact_so_class_attendance_statistics",
    "fact_course_attendences",

    # Legacy support
    "academic_years",
    "semesters",
    "grades",
    "classes",
    "subjects",
    "teacher_assignments",
    "students",
    "enrollments",
    "exam_papers",
    "curriculum_units",
    "exam_competencies",
    "scores",
    "exam_column_mappings",
    "subject_evaluations",
    "student_term_reports",
}

SO_SCHOOL_ID_TABLES = {
    "users",
    "classroom_recordings",
    "dim_homeroom_class",
    "dim_homeroom_class_student",
    "dim_so_assignment",
    "dim_grade_scale_detail",
    "dim_course",
    "fact_gradebooks",
    "fact_gradebooks_moet",
    "fact_so_assignment_grade",
    "fact_overall_academic_records",
    "fact_course_enrolls",
    "fact_behavior_logs",
    "fact_so_homeroom_class_attendances",
    "fact_so_homeroom_class_late_attendances",
    "fact_absent_logs",
    "fact_so_class_attendance_statistics",
    "fact_course_attendences",
    "metadata_index",
}

DIRECT_SCHOOL_ID_TABLES = {
    "schools",
    "academic_years",
    "grades",
    "students",
    "subjects",
    "exam_papers",
}


def is_direct_table(table: exp.Table, select_node: exp.Select) -> bool:
    """Duyệt ngược lên để kiểm tra xem nút Select cha gần nhất của Table có phải là select_node đang xét hay không."""
    parent = table.parent
    while parent:
        if isinstance(parent, exp.Select):
            return parent is select_node
        parent = parent.parent
    return False


class PermissionDeniedError(Exception):
    """Truy vấn nằm ngoài phạm vi phân quyền của user hiện tại."""


DANGEROUS_FUNCTIONS = {
    "pg_sleep",
    "dblink",
    "dblink_connect",
    "pg_read_file",
    "pg_ls_dir",
    "query_to_xml",
    "pg_read_binary_file",
}


def get_user_assignment_constraints(user_id: int | str, user_role: str | None) -> dict:
    """Lấy danh sách các giới hạn homeroom_class_id, grade_id, subject_class_pairs từ teacher_assignments."""
    if not user_role or str(user_role).upper() in ("ADMIN", "PRINCIPAL"):
        return {"is_full_access": True}

    from sqlalchemy import text

    from src.db.session import SessionLocal

    try:
        with SessionLocal() as db_session:
            rows = db_session.execute(text("""
                SELECT role_context, class_id, grade_id, subject_id
                FROM public.teacher_assignments
                WHERE user_id = :uid AND is_active = true
            """), {"uid": int(user_id)}).fetchall()

            if not rows:
                return {"is_full_access": False, "homeroom_class_ids": [], "grade_ids": [], "subject_class_pairs": []}

            homeroom_class_ids = set()
            grade_ids = set()
            subject_class_pairs = set()

            for r in rows:
                role_ctx = str(r[0]).upper()
                cid, gid, subid = r[1], r[2], r[3]
                if "GRADE_HEAD" in role_ctx and gid:
                    grade_ids.add(int(gid))
                elif "HOMEROOM" in role_ctx and cid:
                    homeroom_class_ids.add(int(cid))
                elif "SUBJECT_TEACHER" in role_ctx and cid and subid:
                    subject_class_pairs.add((int(cid), int(subid)))

            # scope_summary thân thiện cho người dùng — KHÔNG lộ tên biến/bảng/ID nội bộ.
            # Bọc riêng để lỗi resolve tên chỉ fallback sang mô tả tổng quát, KHÔNG fail-open.
            scope_parts: list[str] = []
            try:
                all_class_ids = {int(c) for c in homeroom_class_ids}
                if subject_class_pairs:
                    all_class_ids.update(int(c) for c, _ in subject_class_pairs)
                cls_map: dict[int, str] = {}
                if all_class_ids:
                    c_ph = ", ".join(map(str, sorted(all_class_ids)))
                    cls_map = {
                        int(r[0]): r[1]
                        for r in db_session.execute(
                            text(f"SELECT id, code FROM s360.dim_homeroom_class WHERE id IN ({c_ph})")
                        ).fetchall()
                    }
                sub_map: dict[int, str] = {}
                if subject_class_pairs:
                    s_ph = ", ".join(map(str, sorted({int(s) for _, s in subject_class_pairs})))
                    sub_map = {
                        int(r[0]): r[1]
                        for r in db_session.execute(
                            text(f"SELECT id, name FROM s360.dim_subject WHERE id IN ({s_ph})")
                        ).fetchall()
                    }

                if grade_ids:
                    scope_parts.append("khối " + ", ".join(str(g) for g in sorted(grade_ids)))
                if homeroom_class_ids:
                    # GV chủ nhiệm có TOÀN QUYỀN mọi môn của lớp chủ nhiệm — ghi rõ để LLM
                    # không hiểu nhầm "lớp X; môn Y" thành chỉ được phép môn Y.
                    scope_parts.append(
                        "toàn quyền lớp " + ", ".join(
                            dict.fromkeys(cls_map.get(int(c), "lớp được phân công") for c in sorted(homeroom_class_ids))
                        ) + " (mọi môn học của lớp chủ nhiệm)"
                    )
                if subject_class_pairs:
                    scope_parts.append(
                        ", ".join(f"môn {sub_map.get(int(s), 'môn được phân công')}" for c, s in sorted(subject_class_pairs))
                    )
            except Exception:
                # Fallback tổng quát — vẫn GIỮ giới hạn quyền, không lộ ID nội bộ
                if grade_ids:
                    scope_parts.append("khối " + ", ".join(str(g) for g in sorted(grade_ids)))
                if homeroom_class_ids:
                    scope_parts.append("các lớp được phân công")
                if subject_class_pairs:
                    scope_parts.append("các môn được phân công")

            return {
                "is_full_access": False,
                "homeroom_class_ids": list(homeroom_class_ids),
                "grade_ids": list(grade_ids),
                "subject_class_pairs": list(subject_class_pairs),
                "scope_summary": "; ".join(scope_parts) or "không có phân công (không thể truy cập dữ liệu điểm)",
            }
    except Exception as e:
        logger.warning(f"Error fetching teacher assignments for user {user_id}: {e}")
        return {"is_full_access": True}


# Bảng chịu filter RBAC theo phân công giáo viên
_RBAC_TABLES = {
    "fact_gradebooks",
    "fact_gradebooks_moet",
    "fact_overall_academic_records",
    "fact_so_assignment_grade",
    "dim_homeroom_class_student",
}
# Bảng có cột grade_id trực tiếp
_DIRECT_GRADE_TABLES = {
    "fact_gradebooks_moet",
    "fact_overall_academic_records",
    "dim_homeroom_class_student",
}
# Bảng có cặp (homeroom_class_id, subject_id) trực tiếp — dùng cho subject_class_pairs
_SUBJECT_CLASS_TABLES = {"fact_gradebooks", "fact_gradebooks_moet"}


def _rbac_clauses_for_table(t_name: str, alias: str, rbac_meta: dict) -> list[str]:
    """Sinh điều kiện RBAC theo cấu trúc cột thực của bảng.

    - Bảng có cột grade_id trực tiếp -> dùng `{alias}.grade_id IN (...)`.
    - fact_gradebooks (không có grade_id) -> resolve qua s360.dim_homeroom_class.
    - fact_so_assignment_grade (không có class/grade/subject) -> resolve qua
      s360.dim_so_assignment + s360.dim_homeroom_class_student.
    """
    homeroom_ids = rbac_meta.get("homeroom_class_ids") or []
    grade_ids = rbac_meta.get("grade_ids") or []
    pairs = rbac_meta.get("subject_class_pairs") or []
    clauses: list[str] = []

    if t_name == "fact_so_assignment_grade":
        if homeroom_ids:
            cids = ", ".join(map(str, homeroom_ids))
            clauses.append(
                f"{alias}.student_code IN (SELECT student_code FROM s360.dim_homeroom_class_student "
                f"WHERE homeroom_class_id IN ({cids}))"
            )
        if grade_ids:
            gids = ", ".join(map(str, grade_ids))
            clauses.append(
                f"{alias}.assignment_id IN (SELECT assignment_id FROM s360.dim_so_assignment "
                f"WHERE grade_id IN ({gids}))"
            )
        if pairs:
            pair_clauses = [
                f"{alias}.assignment_id IN (SELECT a.assignment_id FROM s360.dim_so_assignment a "
                f"JOIN s360.dim_homeroom_class_student s ON s.grade_id = a.grade_id "
                f"WHERE a.subject_id = {subid} AND s.homeroom_class_id = {cid})"
                for cid, subid in pairs
            ]
            clauses.append(f"({' OR '.join(pair_clauses)})")
        return clauses

    # Các bảng còn lại đều có cột homeroom_class_id
    if homeroom_ids:
        cids = ", ".join(map(str, homeroom_ids))
        clauses.append(f"{alias}.homeroom_class_id IN ({cids})")
    if grade_ids:
        gids = ", ".join(map(str, grade_ids))
        if t_name in _DIRECT_GRADE_TABLES:
            clauses.append(f"{alias}.grade_id IN ({gids})")
        else:  # fact_gradebooks — không có cột grade_id
            clauses.append(
                f"{alias}.homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class "
                f"WHERE grade_id IN ({gids}))"
            )
    if pairs and t_name in _SUBJECT_CLASS_TABLES:
        pair_clauses = [
            f"({alias}.homeroom_class_id = {cid} AND {alias}.subject_id = {subid})"
            for cid, subid in pairs
        ]
        clauses.append(f"({' OR '.join(pair_clauses)})")
    return clauses


def validate_and_secure_sql(
    query: str,
    current_school_id: str,
    user_id: int | str | None = None,
    user_role: str | None = None,
) -> str:
    """Kiểm tra cú pháp SQL, chỉ cho phép SELECT từ danh sách bảng hợp lệ,
    và tự động chèn bộ lọc school_id + phân quyền giáo viên RBAC/ABAC (Tenant & User Isolation).
    """
    # 0. Chặn nhanh từ khóa / hàm nguy hiểm (Chống DoS & System File Access)
    q_lower = query.lower()
    for fn in DANGEROUS_FUNCTIONS:
        if fn in q_lower:
            logger.warning("sql_guardrail_reject", reason="dangerous_function", func=fn, query=query)
            sql_guardrail_rejections_total.labels(reason="dangerous_function").inc()
            raise ValueError(f"Không được phép sử dụng hàm nguy hiểm: {fn}")

    # 0.5. Chặn câu lệnh SQL cố tình wildcard search ILIKE '%...' trên student_name
    import re
    if re.search(r"student_name\s+ILIKE\s+['\"]%[^'\"]*['\"]", query, re.IGNORECASE) or re.search(r"student_name\s+ILIKE\s+['\"]%[^'\"]*%['\"]", query, re.IGNORECASE):
        logger.warning("sql_guardrail_reject", reason="student_name_wildcard_ilike", query=query)
        sql_guardrail_rejections_total.labels(reason="student_name_wildcard_ilike").inc()
        raise ValueError("Chặn an toàn: Không được phép sử dụng ILIKE wildcard (%...) để dò tìm mờ tên học sinh. Vui lòng tra cứu theo mã học sinh hoặc họ tên khớp chính xác.")

    try:
        expression = sqlglot.parse_one(query, read="postgres")
    except Exception as e:
        logger.warning("sql_guardrail_reject", reason="parse_error", error=str(e), query=query)
        sql_guardrail_rejections_total.labels(reason="parse_error").inc()
        raise ValueError(f"Câu lệnh SQL không hợp lệ: {e}")

    # 1. Chặn toàn bộ các câu lệnh thay đổi dữ liệu hoặc có chứa cấu trúc DDL
    for node in expression.walk():
        if isinstance(
            node,
            (
                exp.Drop,
                exp.Update,
                exp.Delete,
                exp.Insert,
                exp.Alter,
                exp.Create,
                exp.Command,
                exp.Transaction,
            ),
        ):
            logger.warning("sql_guardrail_reject", reason="write_or_ddl_statement", query=query)
            sql_guardrail_rejections_total.labels(reason="write_or_ddl_statement").inc()
            raise ValueError("Chỉ được phép thực hiện truy vấn đọc dữ liệu (SELECT).")

    # Kiểm tra gốc của câu lệnh phải là SELECT hoặc UNION
    if not isinstance(expression, (exp.Select, exp.Union)):
        logger.warning("sql_guardrail_reject", reason="not_select_root", query=query)
        sql_guardrail_rejections_total.labels(reason="not_select_root").inc()
        raise ValueError("Chỉ được phép thực hiện truy vấn SELECT.")

    # 2. Thu thập danh sách CTE names để tránh chặn nhầm khi truy vấn CTE
    cte_names = set()
    for cte in expression.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.lower())

    # 3. Kiểm tra whitelist bảng truy cập
    for table in expression.find_all(exp.Table):
        t_name = table.name.lower()
        if t_name not in ALLOWED_TABLES and t_name not in cte_names:
            logger.warning("sql_guardrail_reject", reason="table_not_whitelisted", table=table.name, query=query)
            sql_guardrail_rejections_total.labels(reason="table_not_whitelisted").inc()
            raise ValueError(f"Không được phép truy cập bảng: {table.name}")

    # Lấy thông tin phân công giáo viên nếu có user_id & user_role
    rbac_meta = None
    if user_id and user_role:
        rbac_meta = get_user_assignment_constraints(user_id, user_role)

    # 4. Tự động chèn điều kiện lọc school_id & RBAC vào mệnh đề WHERE của từng SELECT node.
    #    Snapshot danh sách SELECT TRƯỚC khi mutate: các subquery do validator tự inject vào WHERE
    #    không được xử lý lại (tránh điều kiện lặp/trùng trong câu SQL sinh ra).
    select_nodes = list(expression.find_all(exp.Select))
    for select_node in select_nodes:
        tables = [t for t in select_node.find_all(exp.Table) if is_direct_table(t, select_node)]

        constraints = []
        for table in tables:
            t_name = table.name.lower()
            alias = table.alias_or_name

            if t_name in cte_names:
                continue

            if t_name in SO_SCHOOL_ID_TABLES:
                constraints.append(f"{alias}.so_school_id = {current_school_id}")
            elif t_name == "dim_exam":
                # Inject kèm school_id ngay trong subquery (không phụ thuộc pass xử lý lại subquery)
                constraints.append(
                    f"{alias}.id IN (SELECT so_exam_id FROM s360.fact_gradebooks "
                    f"WHERE fact_gradebooks.so_school_id = {current_school_id})"
                )
            elif t_name == "fact_subject_academic_records":
                constraints.append(
                    f"{alias}.overall_record_id IN (SELECT id FROM s360.fact_overall_academic_records "
                    f"WHERE fact_overall_academic_records.so_school_id = {current_school_id})"
                )
            elif t_name == "fact_so_evaluate_process_subjects":
                constraints.append(
                    f"{alias}.student_code IN (SELECT student_code FROM s360.dim_homeroom_class_student "
                    f"WHERE dim_homeroom_class_student.so_school_id = {current_school_id})"
                )
            elif t_name == "dim_homeroom_class_student":
                constraints.append(
                    f"{alias}.homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class "
                    f"WHERE dim_homeroom_class.so_school_id = {current_school_id})"
                )
            elif t_name in DIRECT_SCHOOL_ID_TABLES:
                if t_name == "schools":
                    constraints.append(f"{alias}.id = '{current_school_id}'")
                else:
                    constraints.append(f"{alias}.school_id = '{current_school_id}'")

            # Inject RBAC User Assignment Constraints (theo khả năng cột thực của từng bảng)
            if rbac_meta and not rbac_meta.get("is_full_access", True):
                if t_name in _RBAC_TABLES:
                    rbac_clauses = _rbac_clauses_for_table(t_name, alias, rbac_meta)
                    if rbac_clauses:
                        constraints.append(f"({' OR '.join(rbac_clauses)})")
                    else:
                        # User có role nhưng KHÔNG có phân công phù hợp với bảng này
                        # -> từ chối rõ ràng để agent dừng sớm thay vì hiểu nhầm là không có dữ liệu.
                        raise PermissionDeniedError(
                            "Bạn không có quyền truy cập bảng này theo phân công hiện tại."
                        )

        if constraints:
            where_str = " AND ".join(constraints)
            if select_node.args.get("where"):
                select_node.where(f"({select_node.args['where'].this}) AND ({where_str})", copy=False)
            else:
                select_node.where(where_str, copy=False)

    # 5. Giới hạn số dòng trả về tối đa (Limit Guardrail) để tránh nghẽn RAM / OOM
    if isinstance(expression, (exp.Select, exp.Union)):
        limit_node = expression.args.get("limit")
        needs_limit = True
        if limit_node:
            try:
                val = int(str(limit_node.expression or limit_node.this))
                if val <= 100:
                    needs_limit = False
            except Exception:
                pass
        if needs_limit:
            expression.limit(100, copy=False)

    return expression.sql(dialect="postgres")
