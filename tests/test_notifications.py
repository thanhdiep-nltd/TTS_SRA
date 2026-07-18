"""Test offline (không chạm DB) cho dịch vụ thông báo — đặc biệt RBAC phạm vi gửi chủ động."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.models import enums
from src.models.tables import Notification, Subject, User
from src.schemas.notifications import AnnouncementCreate
from src.services import notifications


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    """DB giả: get() trả theo dict đã cấu hình; execute() trả execute_result cố định."""

    def __init__(self, get_map=None, execute_result=None):
        self._get_map = get_map or {}
        self._execute_result = execute_result or []
        self.added = []
        self.commit_count = 0

    def get(self, model, obj_id):
        return self._get_map.get((model, obj_id))

    def execute(self, _stmt):
        return _FakeResult(self._execute_result)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commit_count += 1


def _user(role, school_id=None, user_id=None):
    return SimpleNamespace(id=user_id or uuid4(), school_id=school_id or uuid4(), role=role)


# ----------------------------- notify() (lõi) -----------------------------


def test_notify_excludes_sender_from_recipients():
    db = _FakeDB()
    a, b = uuid4(), uuid4()
    count = notifications.notify(db, uuid4(), [a, b], enums.NotificationType.ANNOUNCEMENT, "t", "m", sender_id=a)
    assert count == 1
    assert db.added[0].recipient_id == b


def test_notify_dedupes_recipient_ids():
    db = _FakeDB()
    a = uuid4()
    count = notifications.notify(db, uuid4(), [a, a, a], enums.NotificationType.ANNOUNCEMENT, "t", "m")
    assert count == 1
    assert len(db.added) == 1


def test_notify_skips_none_recipient():
    db = _FakeDB()
    count = notifications.notify(db, uuid4(), [None], enums.NotificationType.ANNOUNCEMENT, "t", "m")
    assert count == 0


def test_notify_commits_once_regardless_of_recipient_count():
    db = _FakeDB()
    notifications.notify(db, uuid4(), [uuid4(), uuid4(), uuid4()], enums.NotificationType.ANNOUNCEMENT, "t", "m")
    assert db.commit_count == 1


# ----------------------------- notify_question_submitted_batch -----------------------------


def test_notify_question_submitted_batch_targets_subject_head(monkeypatch):
    subject_id, head_id, school_id, creator_id, item_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(name="Toán")})
    monkeypatch.setattr(notifications, "_subject_head_id", lambda _db, sid: head_id)
    captured = {}
    monkeypatch.setattr(
        notifications,
        "notify",
        lambda db_, school_id_, recipients, type_, title, message, **k: (
            captured.update(recipients=recipients, type_=type_, message=message, **k) or len(recipients)
        ),
    )

    item = SimpleNamespace(
        subject_id=subject_id, grade_number=8, school_id=school_id, created_by=creator_id, id=item_id
    )
    result = notifications.notify_question_submitted_batch(db, [item])

    assert result == 1
    assert captured["recipients"] == [head_id]
    assert captured["type_"] == enums.NotificationType.QUESTION_SUBMITTED
    # sender_id=None (không phải creator_id): đây là nhiệm vụ "cần duyệt", phải báo cả khi người
    # tạo câu chính là Trưởng bộ môn — nếu dùng sender_id=created_by, notify() sẽ tự loại trừ
    # chính người nhận khi 2 vai trò trùng nhau (xem notify_question_submitted_batch).
    assert captured["sender_id"] is None
    assert "1 câu hỏi mới" in captured["message"]


def test_notify_question_submitted_batch_message_counts_multiple_items(monkeypatch):
    subject_id = uuid4()
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(name="KHTN")})
    monkeypatch.setattr(notifications, "_subject_head_id", lambda _db, sid: uuid4())
    captured = {}
    monkeypatch.setattr(
        notifications,
        "notify",
        lambda db_, school_id_, recipients, type_, title, message, **k: captured.update(message=message) or 1,
    )
    items = [
        SimpleNamespace(subject_id=subject_id, grade_number=8, school_id=uuid4(), created_by=uuid4(), id=uuid4())
        for _ in range(3)
    ]
    notifications.notify_question_submitted_batch(db, items)
    assert "3 câu hỏi mới" in captured["message"]


def test_notify_question_submitted_batch_returns_zero_when_no_head(monkeypatch):
    monkeypatch.setattr(notifications, "_subject_head_id", lambda _db, sid: None)
    item = SimpleNamespace(subject_id=uuid4(), grade_number=8, school_id=uuid4(), created_by=uuid4(), id=uuid4())
    assert notifications.notify_question_submitted_batch(_FakeDB(), [item]) == 0


def test_notify_question_submitted_batch_empty_list_returns_zero():
    assert notifications.notify_question_submitted_batch(_FakeDB(), []) == 0


# ----------------------------- notify_item_reviewed -----------------------------


def test_notify_item_reviewed_approved_message_has_no_reason(monkeypatch):
    subject_id = uuid4()
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(name="KHTN")})
    captured = {}
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: captured.update(k) or 1)
    item = SimpleNamespace(
        subject_id=subject_id, school_id=uuid4(), created_by=uuid4(), reviewed_by=uuid4(), id=uuid4()
    )

    notifications.notify_item_reviewed(db, item, approved=True, reason=None)

    assert "đã được DUYỆT" in captured["message"]
    assert "Lý do" not in captured["message"]


def test_notify_item_reviewed_rejected_includes_reason(monkeypatch):
    subject_id = uuid4()
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(name="Toán")})
    captured = {}
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: captured.update(k) or 1)
    item = SimpleNamespace(
        subject_id=subject_id, school_id=uuid4(), created_by=uuid4(), reviewed_by=uuid4(), id=uuid4()
    )

    notifications.notify_item_reviewed(db, item, approved=False, reason="Đáp án sai")

    assert "đã bị TỪ CHỐI" in captured["message"]
    assert "Lý do: Đáp án sai" in captured["message"]


# ----------------------------- notify_exam_finalized -----------------------------


def test_notify_exam_finalized_includes_creator_and_head(monkeypatch):
    subject_id, creator_id, head_id = uuid4(), uuid4(), uuid4()
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(name="Toán")})
    monkeypatch.setattr(notifications, "_subject_head_id", lambda _db, sid: head_id)
    captured = {}
    monkeypatch.setattr(
        notifications,
        "notify",
        lambda db_, school_id_, recipients, *a, **k: captured.update(recipients=set(recipients)) or len(recipients),
    )
    gen = SimpleNamespace(created_by=creator_id, school_id=uuid4(), id=uuid4())
    blueprint = SimpleNamespace(subject_id=subject_id, title="Đề Cuối kỳ Toán")

    notifications.notify_exam_finalized(db, gen, blueprint)

    assert captured["recipients"] == {creator_id, head_id}


def test_notify_exam_finalized_dedupes_when_creator_is_head(monkeypatch):
    subject_id, same = uuid4(), uuid4()
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(name="Toán")})
    monkeypatch.setattr(notifications, "_subject_head_id", lambda _db, sid: same)
    captured = {}
    monkeypatch.setattr(
        notifications,
        "notify",
        lambda db_, school_id_, recipients, *a, **k: captured.update(recipients=set(recipients)) or len(recipients),
    )
    gen = SimpleNamespace(created_by=same, school_id=uuid4(), id=uuid4())
    blueprint = SimpleNamespace(subject_id=subject_id, title="Đề")

    notifications.notify_exam_finalized(db, gen, blueprint)

    assert captured["recipients"] == {same}


# ----------------------------- notify_generation_failed -----------------------------


def test_notify_generation_failed_includes_subject_grade_and_reason(monkeypatch):
    subject_id, school_id, recipient_id = uuid4(), uuid4(), uuid4()
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(name="Toán")})
    captured = {}
    monkeypatch.setattr(
        notifications,
        "notify",
        lambda db_, school_id_, recipients, type_, title, message, **k: (
            captured.update(recipients=recipients, type_=type_, message=message, **k) or len(recipients)
        ),
    )

    result = notifications.notify_generation_failed(db, school_id, recipient_id, subject_id, 7, "Không có ngữ cảnh SGK")

    assert result == 1
    assert captured["recipients"] == [recipient_id]
    assert captured["type_"] == enums.NotificationType.GENERATION_FAILED
    assert "Toán" in captured["message"]
    assert "khối 7" in captured["message"]
    assert "Không có ngữ cảnh SGK" in captured["message"]


def test_notify_generation_failed_handles_missing_subject(monkeypatch):
    """Môn có thể đã bị xóa giữa lúc bấm sinh và lúc luồng nền thất bại — không được crash."""
    subject_id, school_id, recipient_id = uuid4(), uuid4(), uuid4()
    db = _FakeDB(get_map={})  # subject_id KHÔNG có trong get_map -> db.get trả None
    captured = {}
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: captured.update(k) or 1)

    notifications.notify_generation_failed(db, school_id, recipient_id, subject_id, 8, "Lỗi LLM")

    assert "?" in captured["message"]


# ----------------------------- create_announcement: RBAC theo phạm vi -----------------------------


def test_create_announcement_rejects_non_broadcast_role():
    sender = _user(enums.UserRole.SUBJECT_TEACHER)
    payload = AnnouncementCreate(
        scope=enums.AnnouncementScope.INDIVIDUAL, title="t", message="m", recipient_user_id=uuid4()
    )
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.create_announcement(_FakeDB(), sender, payload)


def test_create_announcement_school_scope_allowed_for_principal(monkeypatch):
    sender = _user(enums.UserRole.PRINCIPAL)
    monkeypatch.setattr(notifications, "_active_users_in_school", lambda db, sid: [uuid4(), uuid4()])
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: 2)
    payload = AnnouncementCreate(scope=enums.AnnouncementScope.SCHOOL, title="t", message="m")
    assert notifications.create_announcement(_FakeDB(), sender, payload) == 2


def test_create_announcement_school_scope_denied_for_subject_head():
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    payload = AnnouncementCreate(scope=enums.AnnouncementScope.SCHOOL, title="t", message="m")
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.create_announcement(_FakeDB(), sender, payload)


def test_create_announcement_subject_scope_admin_any_subject(monkeypatch):
    subject_id = uuid4()
    sender = _user(enums.UserRole.ADMIN)
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(school_id=sender.school_id)})
    monkeypatch.setattr(notifications, "_subject_member_ids", lambda db_, sid_, subj_: [uuid4()])
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: 1)
    payload = AnnouncementCreate(scope=enums.AnnouncementScope.SUBJECT, title="t", message="m", subject_id=subject_id)
    assert notifications.create_announcement(db, sender, payload) == 1


def test_create_announcement_subject_scope_head_allowed_for_own_subject(monkeypatch):
    subject_id = uuid4()
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    db = _FakeDB(get_map={(Subject, subject_id): SimpleNamespace(school_id=sender.school_id)})
    monkeypatch.setattr(notifications, "_own_subject_id_as_head", lambda db_, uid: subject_id)
    monkeypatch.setattr(notifications, "_subject_member_ids", lambda db_, sid_, subj_: [uuid4(), uuid4()])
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: 2)
    payload = AnnouncementCreate(scope=enums.AnnouncementScope.SUBJECT, title="t", message="m", subject_id=subject_id)
    assert notifications.create_announcement(db, sender, payload) == 2


def test_create_announcement_subject_scope_head_denied_for_other_subject(monkeypatch):
    own_subject_id, other_subject_id = uuid4(), uuid4()
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    monkeypatch.setattr(notifications, "_own_subject_id_as_head", lambda db_, uid: own_subject_id)
    payload = AnnouncementCreate(
        scope=enums.AnnouncementScope.SUBJECT, title="t", message="m", subject_id=other_subject_id
    )
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.create_announcement(_FakeDB(), sender, payload)


def test_create_announcement_subject_scope_head_denied_when_not_a_head_anywhere(monkeypatch):
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    monkeypatch.setattr(notifications, "_own_subject_id_as_head", lambda db_, uid: None)
    payload = AnnouncementCreate(scope=enums.AnnouncementScope.SUBJECT, title="t", message="m", subject_id=uuid4())
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.create_announcement(_FakeDB(), sender, payload)


def test_create_announcement_individual_scope_admin_any_user(monkeypatch):
    target_id = uuid4()
    sender = _user(enums.UserRole.ADMIN)
    target = SimpleNamespace(id=target_id, school_id=sender.school_id, subject_id=uuid4())
    db = _FakeDB(get_map={(User, target_id): target})
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: 1)
    payload = AnnouncementCreate(
        scope=enums.AnnouncementScope.INDIVIDUAL, title="t", message="m", recipient_user_id=target_id
    )
    assert notifications.create_announcement(db, sender, payload) == 1


def test_create_announcement_individual_scope_head_allowed_for_member(monkeypatch):
    subject_id, target_id = uuid4(), uuid4()
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    target = SimpleNamespace(id=target_id, school_id=sender.school_id, subject_id=subject_id)
    db = _FakeDB(get_map={(User, target_id): target})
    monkeypatch.setattr(notifications, "_own_subject_id_as_head", lambda db_, uid: subject_id)
    monkeypatch.setattr(notifications, "notify", lambda *a, **k: 1)
    payload = AnnouncementCreate(
        scope=enums.AnnouncementScope.INDIVIDUAL, title="t", message="m", recipient_user_id=target_id
    )
    assert notifications.create_announcement(db, sender, payload) == 1


def test_create_announcement_individual_scope_head_denied_for_non_member(monkeypatch):
    subject_id, other_subject_id, target_id = uuid4(), uuid4(), uuid4()
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    target = SimpleNamespace(id=target_id, school_id=sender.school_id, subject_id=other_subject_id)
    db = _FakeDB(get_map={(User, target_id): target})
    monkeypatch.setattr(notifications, "_own_subject_id_as_head", lambda db_, uid: subject_id)
    payload = AnnouncementCreate(
        scope=enums.AnnouncementScope.INDIVIDUAL, title="t", message="m", recipient_user_id=target_id
    )
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.create_announcement(db, sender, payload)


def test_create_announcement_individual_scope_rejects_cross_school_target():
    target_id = uuid4()
    sender = _user(enums.UserRole.ADMIN)
    target = SimpleNamespace(id=target_id, school_id=uuid4(), subject_id=None)  # khác trường
    db = _FakeDB(get_map={(User, target_id): target})
    payload = AnnouncementCreate(
        scope=enums.AnnouncementScope.INDIVIDUAL, title="t", message="m", recipient_user_id=target_id
    )
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.create_announcement(db, sender, payload)


def test_create_announcement_individual_scope_rejects_unknown_target():
    sender = _user(enums.UserRole.ADMIN)
    payload = AnnouncementCreate(
        scope=enums.AnnouncementScope.INDIVIDUAL, title="t", message="m", recipient_user_id=uuid4()
    )
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.create_announcement(_FakeDB(), sender, payload)


# ----------------------------- AnnouncementCreate validation -----------------------------


def test_announcement_create_requires_subject_id_for_subject_scope():
    with pytest.raises(ValueError, match="subject_id"):
        AnnouncementCreate(scope=enums.AnnouncementScope.SUBJECT, title="t", message="m")


def test_announcement_create_requires_recipient_for_individual_scope():
    with pytest.raises(ValueError, match="recipient_user_id"):
        AnnouncementCreate(scope=enums.AnnouncementScope.INDIVIDUAL, title="t", message="m")


def test_announcement_create_school_scope_needs_no_target():
    payload = AnnouncementCreate(scope=enums.AnnouncementScope.SCHOOL, title="t", message="m")
    assert payload.subject_id is None
    assert payload.recipient_user_id is None


# ----------------------------- mark_read -----------------------------


def test_mark_read_returns_false_when_not_found():
    db = _FakeDB()
    assert notifications.mark_read(db, uuid4(), uuid4()) is False


def test_mark_read_returns_false_when_wrong_recipient():
    notif_id = uuid4()
    notif = SimpleNamespace(recipient_id=uuid4(), read_at=None)
    db = _FakeDB(get_map={(Notification, notif_id): notif})
    assert notifications.mark_read(db, uuid4(), notif_id) is False


def test_mark_read_sets_read_at_and_commits():
    notif_id, recipient_id = uuid4(), uuid4()
    notif = SimpleNamespace(recipient_id=recipient_id, read_at=None)
    db = _FakeDB(get_map={(Notification, notif_id): notif})

    assert notifications.mark_read(db, recipient_id, notif_id) is True

    assert notif.read_at is not None
    assert db.commit_count == 1


def test_mark_read_idempotent_does_not_recommit_if_already_read():
    notif_id, recipient_id = uuid4(), uuid4()
    already = datetime.now(UTC)
    notif = SimpleNamespace(recipient_id=recipient_id, read_at=already)
    db = _FakeDB(get_map={(Notification, notif_id): notif})

    assert notifications.mark_read(db, recipient_id, notif_id) is True

    assert notif.read_at == already
    assert db.commit_count == 0


# ----------------------------- list_recipient_candidates -----------------------------


def test_list_recipient_candidates_rejects_non_broadcast_role():
    sender = _user(enums.UserRole.SUBJECT_TEACHER)
    with pytest.raises(notifications.AnnouncementPermissionError):
        notifications.list_recipient_candidates(_FakeDB(), sender, None)


def test_list_recipient_candidates_subject_head_ignores_subject_id_param(monkeypatch):
    own_subject_id, other_subject_id = uuid4(), uuid4()
    member = SimpleNamespace(id=uuid4(), full_name="Cô A")
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    db = _FakeDB(execute_result=[member])
    monkeypatch.setattr(notifications, "_own_subject_id_as_head", lambda db_, uid: own_subject_id)
    captured = {}
    monkeypatch.setattr(
        notifications,
        "_subject_member_ids",
        lambda db_, school_id_, subj_: captured.update(subject_id=subj_) or [member.id],
    )

    result = notifications.list_recipient_candidates(db, sender, other_subject_id)

    assert captured["subject_id"] == own_subject_id  # ép buộc về môn mình, bỏ qua param truyền vào
    assert result == [member]


def test_list_recipient_candidates_subject_head_returns_empty_when_not_a_head():
    sender = _user(enums.UserRole.SUBJECT_HEAD)
    assert notifications.list_recipient_candidates(_FakeDB(), sender, None) == []


def test_list_recipient_candidates_admin_with_subject_id_filters_by_subject(monkeypatch):
    subject_id = uuid4()
    member = SimpleNamespace(id=uuid4(), full_name="Thầy B")
    sender = _user(enums.UserRole.ADMIN)
    db = _FakeDB(execute_result=[member])
    monkeypatch.setattr(notifications, "_subject_member_ids", lambda db_, school_id_, subj_: [member.id])

    result = notifications.list_recipient_candidates(db, sender, subject_id)

    assert result == [member]


def test_list_recipient_candidates_admin_without_subject_id_returns_whole_school(monkeypatch):
    member = SimpleNamespace(id=uuid4(), full_name="Cô C")
    sender = _user(enums.UserRole.PRINCIPAL)
    db = _FakeDB(execute_result=[member])
    monkeypatch.setattr(notifications, "_active_users_in_school", lambda db_, school_id_: [member.id])

    result = notifications.list_recipient_candidates(db, sender, None)

    assert result == [member]


def test_list_recipient_candidates_returns_empty_without_querying_when_no_ids(monkeypatch):
    sender = _user(enums.UserRole.ADMIN)
    monkeypatch.setattr(notifications, "_active_users_in_school", lambda db_, school_id_: [])
    assert notifications.list_recipient_candidates(_FakeDB(), sender, None) == []
