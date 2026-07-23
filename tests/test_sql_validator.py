import pytest

from src.core.security.sql_validator import validate_and_secure_sql


def test_allowed_select_queries():
    """Kiểm tra xem các truy vấn SELECT hợp lệ trên bảng s360 có chạy qua được không."""
    school_id = "1"
    query = "SELECT * FROM s360.fact_gradebooks"
    secured = validate_and_secure_sql(query, school_id)
    assert "fact_gradebooks.so_school_id = 1" in secured


def test_users_table_so_school_id_filter():
    """Kiểm tra lọc bảng users (dùng cột so_school_id)."""
    school_id = "1"
    query = "SELECT * FROM users"
    secured = validate_and_secure_sql(query, school_id)
    assert "users.so_school_id = 1" in secured


def test_block_dml_queries():
    """Kiểm tra xem có chặn chính xác các lệnh DML (INSERT, UPDATE, DELETE) không."""
    school_id = "1"

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("INSERT INTO s360.fact_gradebooks (score_value_numeric) VALUES (10.0)", school_id)

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("UPDATE users SET full_name = 'Hacked'", school_id)

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("DELETE FROM s360.fact_gradebooks", school_id)


def test_block_ddl_queries():
    """Kiểm tra xem có chặn chính xác các lệnh DDL (DROP, ALTER, CREATE) không."""
    school_id = "1"

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("DROP TABLE s360.fact_gradebooks", school_id)

    with pytest.raises(ValueError, match="Chỉ được phép thực hiện truy vấn đọc dữ liệu"):
        validate_and_secure_sql("ALTER TABLE users ADD COLUMN temp TEXT", school_id)


def test_indirect_dim_exam_filter():
    """Kiểm tra lọc gián tiếp bảng dim_exam qua fact_gradebooks.so_school_id = 1."""
    school_id = "1"
    query = "SELECT * FROM s360.dim_exam"
    secured = validate_and_secure_sql(query, school_id)
    assert "dim_exam.id IN (SELECT so_exam_id FROM s360.fact_gradebooks WHERE fact_gradebooks.so_school_id = 1)" in secured


def test_information_schema_allowed():
    """Kiểm tra xem information_schema.columns có được phép truy vấn không."""
    school_id = "1"
    query = "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'dim_school_year'"
    secured = validate_and_secure_sql(query, school_id)
    assert "information_schema.columns" in secured or "columns" in secured


def test_block_unallowed_tables():
    """Kiểm tra xem có chặn chính xác các bảng hệ thống độc hại như pg_catalog.pg_tables không."""
    school_id = "1"

    with pytest.raises(ValueError, match="Không được phép truy cập bảng: pg_tables"):
        validate_and_secure_sql("SELECT * FROM pg_catalog.pg_tables", school_id)


def test_cte_queries():
    """Kiểm tra xem các câu truy vấn có CTE trên s360 có được xử lý đúng không."""
    school_id = "1"
    query = """
    WITH temp_gradebooks AS (
        SELECT * FROM s360.fact_gradebooks
    )
    SELECT * FROM temp_gradebooks
    """
    secured = validate_and_secure_sql(query, school_id)
    assert "fact_gradebooks.so_school_id = 1" in secured
    assert "temp_gradebooks" in secured

