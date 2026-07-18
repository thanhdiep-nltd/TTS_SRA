from src.core.security.sql_validator import validate_and_secure_sql


def test_secure_subquery_in_from():
    """Verify that a subquery in the FROM clause has constraints applied locally inside the subquery and not on the outer select."""
    query = """
    SELECT COUNT(*) AS total_students
    FROM (
        SELECT s.student_id, s.value
        FROM scores s
        WHERE s.status = 'APPROVED'
    ) AS student_pairs
    """
    school_id = "cedf3fb6-564e-402c-9304-6ae485495301"
    secured = validate_and_secure_sql(query, school_id)

    # Check that scores filter is inside the subquery
    assert "students.school_id = 'cedf3fb6-564e-402c-9304-6ae485495301'" in secured
    assert "s.student_id IN" in secured
    # The outer SELECT should have no WHERE clause added for student_pairs alias or scores alias
    assert "student_pairs.student_id" not in secured
    assert "student_pairs WHERE" not in secured
    assert "WHERE student_pairs" not in secured


def test_secure_cte_query():
    """Verify that a CTE query has constraints applied locally inside the CTE block and not on the outer select."""
    query = """
    WITH math_scores AS (
        SELECT student_id, value
        FROM scores
        WHERE status = 'APPROVED'
    )
    SELECT * FROM math_scores
    """
    school_id = "cedf3fb6-564e-402c-9304-6ae485495301"
    secured = validate_and_secure_sql(query, school_id)

    # Check that scores constraints are inside the CTE
    assert "scores.student_id IN" in secured
    assert "students.school_id = 'cedf3fb6-564e-402c-9304-6ae485495301'" in secured
    # Check that outer query doesn't have student_id constraints appended to math_scores CTE
    assert "math_scores.student_id" not in secured
    assert "math_scores WHERE" not in secured


def test_secure_nested_subquery_in_where():
    """Verify that a subquery inside the WHERE clause has constraints applied correctly at its own select scope."""
    query = """
    SELECT name
    FROM classes
    WHERE id IN (
        SELECT class_id
        FROM scores
        WHERE value > 8.0
    )
    """
    school_id = "cedf3fb6-564e-402c-9304-6ae485495301"
    secured = validate_and_secure_sql(query, school_id)

    # Outer query should filter classes
    assert (
        "classes.grade_id IN (SELECT id FROM grades WHERE grades.school_id = 'cedf3fb6-564e-402c-9304-6ae485495301')"
        in secured
    )
    # Inner query should filter scores
    assert (
        "scores.student_id IN (SELECT id FROM students WHERE students.school_id = 'cedf3fb6-564e-402c-9304-6ae485495301')"
        in secured
    )
