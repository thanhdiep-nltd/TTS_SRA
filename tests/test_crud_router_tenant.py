"""Test offline cho cô lập tenant (school) trong make_crud_router — không chạm DB thật.

Gap đã phát hiện qua kiểm thử trình duyệt: GET list của academic-years/semesters/grades/
classes/subjects/curriculum-units/students/enrollments KHÔNG lọc theo school_id, trả về
dữ liệu của MỌI trường cho bất kỳ user nào. Test này khóa lại hành vi cô lập đúng.
"""

from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

from src.api.crud_router import TenantScope, _belongs_to_school, _scope_select
from src.models import tables


def test_scope_select_direct_filters_by_school_id_column():
    school_id = uuid4()
    stmt = _scope_select(select(tables.Grade), tables.Grade, TenantScope(), school_id)
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "grades.school_id" in sql
    assert str(school_id).replace("-", "") in sql.replace("-", "")


def test_scope_select_indirect_joins_parent_and_filters_its_school_id():
    school_id = uuid4()
    scope = TenantScope(direct=False, parent_model=tables.AcademicYear, fk_field="academic_year_id")
    stmt = _scope_select(select(tables.Semester), tables.Semester, scope, school_id)
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "JOIN academic_years" in sql
    assert "academic_years.school_id" in sql
    # KHÔNG được tự bịa ra cột semesters.school_id (bảng này không có cột đó).
    assert "semesters.school_id" not in sql


def test_scope_select_class_via_grade():
    school_id = uuid4()
    scope = TenantScope(direct=False, parent_model=tables.Grade, fk_field="grade_id")
    stmt = _scope_select(select(tables.Class), tables.Class, scope, school_id)
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "JOIN grades" in sql
    assert "grades.school_id" in sql


def test_belongs_to_school_true_when_id_none():
    """obj_id=None nghĩa là field không có trong payload -> bỏ qua kiểm tra, không query DB."""
    assert _belongs_to_school(db=None, model=tables.Grade, tenant=TenantScope(), obj_id=None, school_id=uuid4())


def test_belongs_to_school_true_when_query_finds_row():
    found_id = uuid4()
    fake_db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalar_one_or_none=lambda: found_id))
    result = _belongs_to_school(fake_db, tables.Grade, TenantScope(), found_id, uuid4())
    assert result is True


def test_belongs_to_school_false_when_query_finds_nothing():
    """Trường hợp thật: FK trỏ tới 1 dòng của TRƯỜNG KHÁC -> scoped query không khớp -> None -> False."""
    fake_db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalar_one_or_none=lambda: None))
    result = _belongs_to_school(fake_db, tables.AcademicYear, TenantScope(), uuid4(), uuid4())
    assert result is False
