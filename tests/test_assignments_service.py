"""Test offline cho quy tắc validate phân công — không chạm DB thật."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.models import enums
from src.schemas.user import AssignmentCreate
from src.services.assignments import (
    NO_ASSIGNMENT_ROLES,
    validate_context_fields,
    validate_role_context,
)


def _payload(context: enums.RoleContext, **kw) -> AssignmentCreate:
    return AssignmentCreate(user_id=uuid4(), academic_year_id=uuid4(), role_context=context, **kw)


# ---- Tổ hợp field theo role_context ----


def test_subject_teacher_requires_class_and_subject():
    with pytest.raises(HTTPException) as exc:
        validate_context_fields(_payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4()))
    assert exc.value.status_code == 422
    assert "Môn" in exc.value.detail


def test_subject_teacher_forbids_grade():
    with pytest.raises(HTTPException) as exc:
        validate_context_fields(
            _payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4(), subject_id=uuid4(), grade_id=uuid4())
        )
    assert exc.value.status_code == 422
    assert "Khối" in exc.value.detail


def test_subject_teacher_valid_combo_passes():
    validate_context_fields(_payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4(), subject_id=uuid4()))


@pytest.mark.parametrize("context", [enums.RoleContext.HOMEROOM_PRIMARY, enums.RoleContext.HOMEROOM_SECONDARY])
def test_homeroom_requires_class_only(context):
    validate_context_fields(_payload(context, class_id=uuid4()))
    with pytest.raises(HTTPException):
        validate_context_fields(_payload(context))
    with pytest.raises(HTTPException):
        validate_context_fields(_payload(context, class_id=uuid4(), subject_id=uuid4()))


def test_grade_head_requires_grade_only():
    validate_context_fields(_payload(enums.RoleContext.GRADE_HEAD, grade_id=uuid4()))
    with pytest.raises(HTTPException):
        validate_context_fields(_payload(enums.RoleContext.GRADE_HEAD, grade_id=uuid4(), class_id=uuid4()))


def test_subject_head_requires_subject_only():
    validate_context_fields(_payload(enums.RoleContext.SUBJECT_HEAD, subject_id=uuid4()))
    with pytest.raises(HTTPException):
        validate_context_fields(_payload(enums.RoleContext.SUBJECT_HEAD, subject_id=uuid4(), grade_id=uuid4()))


# ---- Role user ↔ role_context ----


@pytest.mark.parametrize("role", [enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL])
def test_admin_principal_receive_no_assignment(role):
    user = SimpleNamespace(role=role)
    with pytest.raises(HTTPException) as exc:
        validate_role_context(user, enums.RoleContext.SUBJECT_TEACHER)
    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    "role",
    [enums.UserRole.SUBJECT_TEACHER, enums.UserRole.SUBJECT_HEAD, enums.UserRole.HOMEROOM_TEACHER_SECONDARY],
)
@pytest.mark.parametrize("context", list(enums.RoleContext))
def test_teaching_roles_can_receive_any_role_context(role, context):
    """RBAC thực tế (rbac.py) dựa hoàn toàn vào role_context của phân công, không vào User.role —
    dữ liệu thật chỉ có role SUBJECT_TEACHER/SUBJECT_HEAD nhưng vẫn giữ phân công HOMEROOM/GRADE_HEAD."""
    validate_role_context(SimpleNamespace(role=role), context)


def test_no_assignment_roles_is_admin_and_principal_only():
    assert NO_ASSIGNMENT_ROLES == {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}


# ---- Kiểm tra phụ thuộc DB (fake db kiểu SimpleNamespace) ----

from src.services.assignments import (  # noqa: E402
    _class_homeroom_holder,
    _duplicate_exists,
    _validate_refs,
    deactivate_mismatched,
)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        seq = self._value if isinstance(self._value, list) else [self._value]
        return SimpleNamespace(first=lambda: seq[0] if seq else None, all=lambda: seq)


def _fake_db(value):
    return SimpleNamespace(execute=lambda _stmt: _FakeResult(value))


def test_duplicate_exists_true_when_row_found():
    p = _payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4(), subject_id=uuid4())
    assert _duplicate_exists(_fake_db(uuid4()), p) is True
    assert _duplicate_exists(_fake_db(None), p) is False


def test_class_homeroom_holder_returns_teacher_name():
    p = _payload(enums.RoleContext.HOMEROOM_SECONDARY, class_id=uuid4())
    assert _class_homeroom_holder(_fake_db(["Cô Lan"]), p) == "Cô Lan"
    assert _class_homeroom_holder(_fake_db([]), p) is None


def test_validate_refs_rejects_class_of_other_school():
    p = _payload(enums.RoleContext.HOMEROOM_SECONDARY, class_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        _validate_refs(_fake_db(None), p, uuid4())
    assert exc.value.status_code == 422
    assert "Lớp" in exc.value.detail


def test_validate_refs_rejects_class_of_other_year():
    p = _payload(enums.RoleContext.HOMEROOM_SECONDARY, class_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        _validate_refs(_fake_db(uuid4()), p, uuid4())  # trả về year_id KHÁC payload.academic_year_id
    assert "niên khóa" in exc.value.detail


def test_validate_refs_accepts_class_of_correct_year():
    p = _payload(enums.RoleContext.HOMEROOM_SECONDARY, class_id=uuid4())
    _validate_refs(_fake_db(p.academic_year_id), p, uuid4())  # không raise


def test_deactivate_mismatched_keeps_assignments_when_new_role_still_teaches():
    a1 = SimpleNamespace(role_context=enums.RoleContext.HOMEROOM_SECONDARY, is_active=True)
    a2 = SimpleNamespace(role_context=enums.RoleContext.SUBJECT_TEACHER, is_active=True)
    user = SimpleNamespace(id=uuid4())
    count = deactivate_mismatched(_fake_db([a1, a2]), user, enums.UserRole.SUBJECT_TEACHER)
    assert count == 0
    assert a1.is_active is True
    assert a2.is_active is True


def test_deactivate_mismatched_disables_all_when_new_role_is_admin_or_principal():
    a1 = SimpleNamespace(role_context=enums.RoleContext.HOMEROOM_SECONDARY, is_active=True)
    a2 = SimpleNamespace(role_context=enums.RoleContext.SUBJECT_TEACHER, is_active=True)
    user = SimpleNamespace(id=uuid4())
    count = deactivate_mismatched(_fake_db([a1, a2]), user, enums.UserRole.PRINCIPAL)
    assert count == 2
    assert a1.is_active is False
    assert a2.is_active is False


# ---- Coverage: ghép dữ liệu lớp/môn/phân công (pure) ----

from src.services.assignments import _match_level, build_coverage_rows  # noqa: E402


def test_match_level_all_applies_everywhere():
    assert _match_level(enums.SchoolLevel.ALL, enums.SchoolLevel.SECONDARY) is True
    assert _match_level(enums.SchoolLevel.SECONDARY, enums.SchoolLevel.SECONDARY) is True
    assert _match_level(enums.SchoolLevel.HIGH, enums.SchoolLevel.SECONDARY) is False


def test_build_coverage_rows_marks_missing_homeroom_and_subject():
    class_id, subject_id = uuid4(), uuid4()
    classes = [SimpleNamespace(id=class_id, name="6A1", grade_name="Khối 6", school_level=enums.SchoolLevel.SECONDARY)]
    subjects = [
        SimpleNamespace(id=subject_id, name="Toán", applicable_level=enums.SchoolLevel.ALL),
        SimpleNamespace(id=uuid4(), name="GDQP-AN", applicable_level=enums.SchoolLevel.HIGH),  # không áp cấp 2
    ]
    homeroom = {}
    subject_teachers = {(class_id, subject_id): "Thầy Nam"}
    rows = build_coverage_rows(classes, subjects, homeroom, subject_teachers)
    assert len(rows) == 1
    assert rows[0]["homeroom_teacher"] is None
    assert len(rows[0]["subjects"]) == 1  # môn HIGH bị loại
    assert rows[0]["subjects"][0]["teacher_name"] == "Thầy Nam"


# ---- Reassign atomic (tab "Theo lớp") ----

from src.services.assignments import (  # noqa: E402
    SLOT_ROLE_CONTEXTS,
    _deactivate_slot_occupants,
    reassign_class_slot,
)


class _RecordingDb:
    """Fake Session cho reassign_class_slot: trả occupants cho SELECT list, giá trị cố định
    cho scalar_one_or_none (dùng bởi _validate_year/_validate_refs/_duplicate_exists), đếm commit()."""

    def __init__(self, occupants, get_user=None, scalar_value=None):
        self._occupants = occupants
        self._get_user = get_user
        self._scalar_value = scalar_value
        self.commits = 0
        self.added = []
        self.executed_statements = []

    def execute(self, stmt):
        self.executed_statements.append(stmt)
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: self._occupants, first=lambda: None),
            scalar_one_or_none=lambda: self._scalar_value,
        )

    def get(self, _model, _id):
        return self._get_user

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def refresh(self, _obj):
        pass

    def commit(self):
        self.commits += 1


def test_slot_role_contexts_excludes_grade_and_subject_head():
    assert set(SLOT_ROLE_CONTEXTS) == {
        enums.RoleContext.HOMEROOM_PRIMARY,
        enums.RoleContext.HOMEROOM_SECONDARY,
        enums.RoleContext.SUBJECT_TEACHER,
    }


def test_deactivate_slot_occupants_disables_found_rows_without_commit():
    a1 = SimpleNamespace(is_active=True)
    a2 = SimpleNamespace(is_active=True)
    db = _RecordingDb([a1, a2])
    p = _payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4(), subject_id=uuid4())
    _deactivate_slot_occupants(db, p)
    assert a1.is_active is False
    assert a2.is_active is False
    assert db.commits == 0


def test_reassign_locks_class_row_before_deactivating_occupant():
    """Race condition fix: khóa dòng classes (FOR UPDATE) trước khi đọc/ghi occupant, để 2
    request reassign đồng thời trên CÙNG 1 lớp bị serialize thay vì cùng tạo 2 bản ghi active."""
    old = SimpleNamespace(is_active=True)
    db = _RecordingDb([old])
    p = _payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4(), subject_id=uuid4())
    with patch("src.services.assignments._validate_create", return_value=SimpleNamespace()):
        reassign_class_slot(db, p)
    first_stmt = db.executed_statements[0]
    compiled = str(first_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in compiled
    assert "classes" in compiled


def test_reassign_rejects_role_context_outside_slot_contexts():
    p = _payload(enums.RoleContext.GRADE_HEAD, grade_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        reassign_class_slot(_RecordingDb([]), p)
    assert exc.value.status_code == 422


def test_reassign_rejects_missing_class_id():
    p = _payload(enums.RoleContext.SUBJECT_TEACHER, subject_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        reassign_class_slot(_RecordingDb([]), p)
    assert exc.value.status_code == 422


def test_reassign_does_not_commit_when_validation_fails():
    """GV không tồn tại -> _validate_create raise 404 -> KHÔNG được commit (occupant cũ phải rollback)."""
    old = SimpleNamespace(is_active=True)
    db = _RecordingDb([old], get_user=None)  # db.get(User, ...) -> None -> "Giáo viên không tồn tại"
    p = _payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4(), subject_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        reassign_class_slot(db, p)
    assert exc.value.status_code == 404
    assert old.is_active is False  # đã bị đổi trong bộ nhớ nhưng KHÔNG commit
    assert db.commits == 0


def test_reassign_commits_once_when_valid():
    """Không test lại logic _validate_create (đã có test riêng) — chỉ test reassign_class_slot
    gọi đúng trình tự: deactivate occupant cũ -> validate -> tạo mới -> commit đúng 1 lần."""
    old = SimpleNamespace(is_active=True)
    db = _RecordingDb([old])
    p = _payload(enums.RoleContext.SUBJECT_TEACHER, class_id=uuid4(), subject_id=uuid4())
    with patch("src.services.assignments._validate_create", return_value=SimpleNamespace()):
        result = reassign_class_slot(db, p)
    assert old.is_active is False
    assert db.commits == 1
    assert len(db.added) == 1
    assert result is db.added[0]


# ---- Danh sách GV cho picker (tab "Theo lớp") ----

from src.services.assignments import list_school_teachers  # noqa: E402


def test_list_school_teachers_excludes_admin_and_principal_via_query():
    """Không test SQL sinh ra (đã có pattern test_scope_select ở tests/test_crud_router_tenant.py
    cho việc đó) — chỉ test hàm gọi đúng execute() và map đúng field."""
    fake_rows = [
        SimpleNamespace(id=uuid4(), full_name="Cô Lan", subject_id=uuid4()),
        SimpleNamespace(id=uuid4(), full_name="Thầy Nam", subject_id=None),
    ]
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(all=lambda: fake_rows))
    result = list_school_teachers(db, uuid4())
    assert result == fake_rows
