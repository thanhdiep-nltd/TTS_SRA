import sqlglot
import sqlglot.expressions as exp

from src.observability import logger, sql_guardrail_rejections_total

ALLOWED_TABLES = {
    "schools",
    "users",
    "refresh_tokens",
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
    "audit_logs",
    "ai_sessions",
    "ai_messages",
    "report_schedules",
}

DIRECT_SCHOOL_ID_TABLES = {
    "schools",
    "users",
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


def validate_and_secure_sql(query: str, current_school_id: str) -> str:
    """Kiểm tra cú pháp SQL, chỉ cho phép SELECT từ danh sách bảng hợp lệ,

    và tự động chèn bộ lọc school_id để đảm bảo phân quyền trường học (Tenant Isolation).
    """
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

            if t_name in DIRECT_SCHOOL_ID_TABLES:
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
