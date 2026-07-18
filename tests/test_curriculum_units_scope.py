"""Test offline cho GET /curriculum-units (lọc đúng môn + khối) — không chạm DB thật.

Bug thật phát hiện qua kiểm thử: route GET list mặc định (CRUD generic) không lọc gì,
nên Trưởng bộ môn Toán thấy lẫn chủ đề của môn khác (vd KHTN) cùng khối. Route
list_curriculum_units thay thế nó, BẮT BUỘC subject_id, tránh lặp lại lỗi này.
"""

from types import SimpleNamespace
from uuid import uuid4

from src.api.v1.school import list_curriculum_units


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self):
        self.last_stmt = None

    def execute(self, stmt):
        self.last_stmt = stmt
        return _FakeResult([])


def _user(school_id=None):
    return SimpleNamespace(school_id=school_id or uuid4())


def _norm(uuid_obj) -> str:
    return str(uuid_obj).replace("-", "")


def test_list_curriculum_units_filters_by_subject_id():
    db = _FakeDB()
    subject_id = uuid4()
    list_curriculum_units(subject_id=subject_id, grade_number=None, db=db, user=_user())
    sql = str(db.last_stmt.compile(compile_kwargs={"literal_binds": True})).replace("-", "")
    assert "curriculum_units.subject_id" in sql
    assert _norm(subject_id) in sql


def test_list_curriculum_units_filters_by_school_via_subject_join():
    db = _FakeDB()
    school_id = uuid4()
    list_curriculum_units(subject_id=uuid4(), grade_number=None, db=db, user=_user(school_id=school_id))
    sql = str(db.last_stmt.compile(compile_kwargs={"literal_binds": True})).replace("-", "")
    assert "JOIN subjects" in sql
    assert "subjects.school_id" in sql
    assert _norm(school_id) in sql


def test_list_curriculum_units_filters_by_grade_when_given():
    db = _FakeDB()
    list_curriculum_units(subject_id=uuid4(), grade_number=8, db=db, user=_user())
    sql = str(db.last_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "WHERE" in sql and "curriculum_units.grade_number = 8" in sql


def test_list_curriculum_units_omits_grade_filter_when_not_given():
    db = _FakeDB()
    list_curriculum_units(subject_id=uuid4(), grade_number=None, db=db, user=_user())
    sql = str(db.last_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "curriculum_units.grade_number =" not in sql
