import sqlglot
import sqlglot.expressions as exp

from src.observability import logger, sql_guardrail_rejections_total

ALLOWED_TABLES = {
    # Metadata / System tables for LLM self-correction
    "columns",
    "tables",

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

    # S360 Dimensions
    "dim_school_year",
    "dim_homeroom_class",
    "dim_homeroom_class_student",
    "dim_subject",
    "dim_exam",
    "dim_exam_moet",
    "dim_so_assignment",
    "dim_grade_scale_detail",

    # S360 Facts
    "fact_gradebooks",
    "fact_gradebooks_moet",
    "fact_so_assignment_grade",
    "fact_subject_academic_records",
    "fact_overall_academic_records",
    "fact_course_enrolls",
    "fact_so_evaluate_process_subjects",

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
    "dim_so_assignment",
    "dim_grade_scale_detail",
    "fact_gradebooks",
    "fact_gradebooks_moet",
    "fact_so_assignment_grade",
    "fact_overall_academic_records",
    "fact_course_enrolls",
    "fact_so_evaluate_process_subjects",
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


DANGEROUS_FUNCTIONS = {
    "pg_sleep",
    "dblink",
    "dblink_connect",
    "pg_read_file",
    "pg_ls_dir",
    "query_to_xml",
    "pg_read_binary_file",
}


def validate_and_secure_sql(query: str, current_school_id: str) -> str:
    """Kiểm tra cú pháp SQL, chỉ cho phép SELECT từ danh sách bảng hợp lệ,

    và tự động chèn bộ lọc school_id để đảm bảo phân quyền trường học (Tenant Isolation).
    """
    # 0. Chặn nhanh từ khóa / hàm nguy hiểm (Chống DoS & System File Access)
    q_lower = query.lower()
    for fn in DANGEROUS_FUNCTIONS:
        if fn in q_lower:
            logger.warning("sql_guardrail_reject", reason="dangerous_function", func=fn, query=query)
            sql_guardrail_rejections_total.labels(reason="dangerous_function").inc()
            raise ValueError(f"Không được phép sử dụng hàm nguy hiểm: {fn}")

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

    # 4. Tự động chèn điều kiện lọc school_id vào mệnh đề WHERE của từng SELECT node
    for select_node in expression.find_all(exp.Select):
        # Lấy các Table trực thuộc select_node hiện tại (không quét sâu xuống subqueries của nó)
        tables = [t for t in select_node.find_all(exp.Table) if is_direct_table(t, select_node)]

        constraints = []
        for table in tables:
            t_name = table.name.lower()
            alias = table.alias_or_name

            # Bỏ qua CTE name
            if t_name in cte_names:
                continue

            if t_name in SO_SCHOOL_ID_TABLES:
                constraints.append(f"{alias}.so_school_id = {current_school_id}")
            elif t_name == "dim_exam":
                constraints.append(f"{alias}.id IN (SELECT so_exam_id FROM s360.fact_gradebooks)")
            elif t_name == "fact_subject_academic_records":
                constraints.append(f"{alias}.overall_record_id IN (SELECT id FROM s360.fact_overall_academic_records)")
            elif t_name == "dim_homeroom_class_student":
                constraints.append(f"{alias}.homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class)")
            elif t_name in DIRECT_SCHOOL_ID_TABLES:
                if t_name == "schools":
                    constraints.append(f"{alias}.id = '{current_school_id}'")
                else:
                    constraints.append(f"{alias}.school_id = '{current_school_id}'")
            elif t_name == "classes":
                constraints.append(f"{alias}.grade_id IN (SELECT id FROM grades)")
            elif t_name == "scores":
                constraints.append(f"{alias}.student_id IN (SELECT id FROM students)")
            elif t_name == "enrollments":
                constraints.append(f"{alias}.student_id IN (SELECT id FROM students)")
            elif t_name == "semesters":
                constraints.append(f"{alias}.academic_year_id IN (SELECT id FROM academic_years)")
            elif t_name in ("subject_evaluations", "student_term_reports"):
                constraints.append(f"{alias}.student_id IN (SELECT id FROM students)")

        if constraints:
            # Gộp các điều kiện bảo mật mới bằng AND
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
