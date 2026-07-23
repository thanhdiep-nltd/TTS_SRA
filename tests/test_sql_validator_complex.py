from src.core.security.sql_validator import validate_and_secure_sql


def test_secure_subquery_in_from():
    """Verify that a subquery in the FROM clause has constraints applied locally inside the subquery and not on the outer select."""
    query = """
    SELECT COUNT(*) AS total_records
    FROM (
        SELECT g.student_code, g.score_value_numeric
        FROM s360.fact_gradebooks g
        WHERE g.score_category = 'FINAL'
    ) AS grade_records
    """
    school_id = "1"
    secured = validate_and_secure_sql(query, school_id)

    # Check that fact_gradebooks filter is inside the subquery
    assert "g.so_school_id = 1" in secured
    assert "grade_records.student_code" not in secured


def test_secure_cte_query():
    """Verify that a CTE query has constraints applied locally inside the CTE block and not on the outer select."""
    query = """
    WITH math_scores AS (
        SELECT student_code, score_value_numeric
        FROM s360.fact_gradebooks
        WHERE score_category = 'FINAL'
    )
    SELECT * FROM math_scores
    """
    school_id = "1"
    secured = validate_and_secure_sql(query, school_id)

    # Check that fact_gradebooks constraints are inside the CTE
    assert "fact_gradebooks.so_school_id = 1" in secured
    assert "math_scores.student_code" not in secured

