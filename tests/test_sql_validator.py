import pytest

from src.core.security.sql_validator import validate_and_secure_sql


def test_allowed_select_queries():
    """Kiểm tra xem các truy vấn SELECT hợp lệ có chạy qua được không."""
    school_id = "00000000-0000-0000-0000-000000000001"
    query = "SELECT * FROM students"
    secured = validate_and_secure_sql(query, school_id)
    assert "students.school_id = '00000000-0000-0000-0000-000000000001'" in secured


def test_schools_table_id_filter():
    """Kiểm tra lọc bảng schools (dùng cột id làm school_id)."""
    school_id = "00000000-0000-0000-0000-000000000001"
    query = "SELECT * FROM schools"
    secured = validate_and_secure_sql(query, school_id)
    assert "schools.id = '00000000-0000-0000-0000-000000000001'" in secured


def test_block_dml_queries():
    """Kiểm tra xem có chặn chính xác các lệnh DML (INSERT, UPDATE, DELETE) không."""
    school_id = "00000000-0000-0000-0000-000000000001"

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("INSERT INTO scores (value) VALUES (10.0)", school_id)

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("UPDATE students SET full_name = 'Hacked'", school_id)

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("DELETE FROM scores", school_id)


def test_block_ddl_queries():
    """Kiểm tra xem có chặn chính xác các lệnh DDL (DROP, ALTER, CREATE) không."""
    school_id = "00000000-0000-0000-0000-000000000001"

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("DROP TABLE scores", school_id)

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("ALTER TABLE students ADD COLUMN temp TEXT", school_id)


def test_block_unallowed_tables():
    """Kiểm tra xem có chặn chính xác các bảng hệ thống hoặc không được phép không."""
    school_id = "00000000-0000-0000-0000-000000000001"

    with pytest.raises(ValueError, match="Không được phép truy cập bảng: pg_tables"):
        validate_and_secure_sql("SELECT * FROM pg_catalog.pg_tables", school_id)

    with pytest.raises(ValueError, match="Không được phép truy cập bảng: tables"):
        validate_and_secure_sql("SELECT * FROM information_schema.tables", school_id)


def test_indirect_table_filters():
    """Kiểm tra lọc các bảng gián tiếp (như classes và scores)."""
    school_id = "00000000-0000-0000-0000-000000000001"

    secured_classes = validate_and_secure_sql("SELECT * FROM classes", school_id)
    assert (
        "classes.grade_id IN (SELECT id FROM grades WHERE grades.school_id = '00000000-0000-0000-0000-000000000001')"
        in secured_classes
    )

    secured_scores = validate_and_secure_sql("SELECT * FROM scores", school_id)
    assert (
        "scores.student_id IN (SELECT id FROM students WHERE students.school_id = '00000000-0000-0000-0000-000000000001')"
        in secured_scores
    )


def test_cte_queries():
    """Kiểm tra xem các câu truy vấn có CTE có được xử lý đúng không."""
    school_id = "00000000-0000-0000-0000-000000000001"
    query = """
    WITH temp_students AS (
        SELECT * FROM students
    )
    SELECT * FROM temp_students
    """
    secured = validate_and_secure_sql(query, school_id)
    # Lọc ở trong CTE với bảng sinh viên thật
    assert "students.school_id = '00000000-0000-0000-0000-000000000001'" in secured
    # Không chặn bảng ảo temp_students
    assert "temp_students" in secured
