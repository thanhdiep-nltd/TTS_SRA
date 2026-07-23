from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.agents.graph import agent
from src.api.deps import get_current_user, get_db
from src.main import app
from src.models import enums
from src.models.tables import AiMessage, AiSession, User
from src.repositories import chat_repo

# Tạo user test cố định
test_user_id = 1
test_user = User(
    id=1,
    so_school_id=1,
    email="teacher_test@school.edu.vn",
    full_name="Giáo Viên Test",
    role=enums.UserRole.SUBJECT_TEACHER,
    is_active=True,
)


def create_mock_session(session_id, user_id, title="Session Title", is_active=True):
    now = datetime.now()
    return AiSession(
        id=session_id,
        user_id=user_id,
        title=title,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def create_mock_message(message_id, session_id, role, content):
    return AiMessage(
        id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        created_at=datetime.now(),
    )


@pytest_asyncio.fixture
async def override_deps():
    """Ghi đè dependencies của FastAPI để chạy offline test."""
    mock_db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: mock_db
    yield mock_db
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_client():
    """Async Client chuyên biệt cho test file này."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_sessions_list(test_client, override_deps, monkeypatch):
    """Test lấy danh sách các chat session của user."""
    session_id = uuid4()

    mock_session = create_mock_session(session_id, test_user_id, "Session 1")
    # Mock hàm repo
    monkeypatch.setattr(chat_repo, "get_active_sessions", lambda db, u_id: [mock_session])

    response = await test_client.get("/api/v1/chat/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(session_id)
    assert data[0]["title"] == "Session 1"


@pytest.mark.asyncio
async def test_get_messages_owner(test_client, override_deps, monkeypatch):
    """Test lấy tin nhắn của session mình sở hữu (thành công)."""
    session_id = uuid4()

    mock_session = create_mock_session(session_id, test_user_id, "Session 1")
    mock_msg = create_mock_message(uuid4(), session_id, enums.AiSessionRole.user, "Hello Test")

    monkeypatch.setattr(chat_repo, "get_session", lambda db, s_id: mock_session)
    monkeypatch.setattr(chat_repo, "get_session_messages", lambda db, s_id, limit: [mock_msg])

    response = await test_client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["content"] == "Hello Test"


@pytest.mark.asyncio
async def test_get_messages_non_owner(test_client, override_deps, monkeypatch):
    """Test lấy tin nhắn của session của người khác (phải trả về 403)."""
    session_id = uuid4()

    mock_session = create_mock_session(session_id, uuid4(), "Session của người khác")

    monkeypatch.setattr(chat_repo, "get_session", lambda db, s_id: mock_session)

    response = await test_client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert response.status_code == 403
    assert response.json()["detail"] == "Bạn không có quyền truy cập phiên chat này"


@pytest.mark.asyncio
async def test_rename_session_permission(test_client, override_deps, monkeypatch):
    """Test đổi tên session kiểm tra quyền sở hữu."""
    session_id = uuid4()

    # Thử đổi tên session của người khác -> 403
    mock_session_other = create_mock_session(session_id, uuid4(), "Old Title")
    monkeypatch.setattr(chat_repo, "get_session", lambda db, s_id: mock_session_other)

    response = await test_client.patch(f"/api/v1/chat/sessions/{session_id}", json={"title": "New Title"})
    assert response.status_code == 403

    # Đổi tên session của mình -> Thành công (200)
    mock_session_mine = create_mock_session(session_id, test_user_id, "Old Title")
    monkeypatch.setattr(chat_repo, "get_session", lambda db, s_id: mock_session_mine)
    monkeypatch.setattr(
        chat_repo, "update_session_title", lambda db, sess, title: create_mock_session(session_id, test_user_id, title)
    )

    response = await test_client.patch(f"/api/v1/chat/sessions/{session_id}", json={"title": "New Title"})
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"


@pytest.mark.asyncio
async def test_delete_session_permission(test_client, override_deps, monkeypatch):
    """Test xóa session kiểm tra quyền sở hữu."""
    session_id = uuid4()

    # Thử xóa session của người khác -> 403
    mock_session_other = create_mock_session(session_id, uuid4())
    monkeypatch.setattr(chat_repo, "get_session", lambda db, s_id: mock_session_other)

    response = await test_client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert response.status_code == 403

    # Xóa session của mình -> Thành công (204)
    mock_session_mine = create_mock_session(session_id, test_user_id)
    monkeypatch.setattr(chat_repo, "get_session", lambda db, s_id: mock_session_mine)

    # Mock soft delete
    soft_deleted = False

    def mock_soft_delete(db, sess):
        nonlocal soft_deleted
        soft_deleted = True

    monkeypatch.setattr(chat_repo, "soft_delete_session", mock_soft_delete)

    response = await test_client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert response.status_code == 204
    assert soft_deleted is True


@pytest.mark.asyncio
async def test_chat_creation_and_agent_call(test_client, override_deps, monkeypatch):
    """Test gửi tin nhắn chat, tự động khởi tạo session và gọi agent."""
    import json

    session_id = uuid4()

    # Mock các hàm của repo
    mock_session = create_mock_session(session_id, test_user_id, "Test Chat")
    monkeypatch.setattr(chat_repo, "create_session", lambda db, user_id, title: mock_session)
    monkeypatch.setattr(chat_repo, "get_session_messages", lambda db, s_id, limit: [])

    created_messages = []

    def mock_create_message(db, session_id, role, content, *args, **kwargs):
        msg = create_mock_message(uuid4(), session_id, role, content)
        created_messages.append(msg)
        return msg

    monkeypatch.setattr(chat_repo, "create_message", mock_create_message)

    # Mock agent astream_events dưới dạng async generator
    async def mock_astream_events(*args, **kwargs):
        yield {"event": "on_chain_end", "data": {"output": {"response": "Agent answer test"}}}

    monkeypatch.setattr(agent, "astream_events", mock_astream_events)

    # Gửi request không kèm session_id để tạo mới
    response = await test_client.post("/api/v1/chat", json={"message": "Câu hỏi phân tích điểm"})

    assert response.status_code == 200

    # Parse SSE events từ stream text
    content = response.text
    lines = content.strip().split("\n\n")
    events = []
    for line in lines:
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    session_id_event = next(e for e in events if e["type"] == "session_id")
    token_events = [e["content"] for e in events if e["type"] == "token"]
    ai_response = "".join(token_events)

    assert session_id_event["content"] == str(session_id)
    assert ai_response == "Agent answer test"

    # Kiểm tra xem có lưu cả tin nhắn của user và reply của AI vào DB không
    assert len(created_messages) == 2
    assert created_messages[0].role == enums.AiSessionRole.user
    assert created_messages[1].role == enums.AiSessionRole.assistant


@pytest.mark.asyncio
async def test_chat_history_does_not_repeat_fallback(test_client, override_deps, monkeypatch):
    """Test gửi tin nhắn mới trong một session có lịch sử cũ, không bị lặp lại tin nhắn cũ."""
    import json

    session_id = uuid4()

    # Session đã có lịch sử cũ
    mock_session = create_mock_session(session_id, test_user_id, "Old Chat")

    # 2 tin nhắn cũ (1 User, 1 AI chứa nội dung cũ)
    old_msg_user = create_mock_message(uuid4(), session_id, enums.AiSessionRole.user, "Show me top student")
    old_msg_ai = create_mock_message(uuid4(), session_id, enums.AiSessionRole.assistant, "Top student is Nguyen Van A")

    monkeypatch.setattr(chat_repo, "get_session", lambda db, s_id: mock_session)
    # Trả về 2 tin nhắn lịch sử cũ
    monkeypatch.setattr(chat_repo, "get_session_messages", lambda db, s_id, limit: [old_msg_user, old_msg_ai])

    created_messages = []

    def mock_create_message(db, session_id, role, content, generated_sql=None, sources=None):
        msg = create_mock_message(uuid4(), session_id, role, content)
        created_messages.append(msg)
        return msg

    monkeypatch.setattr(chat_repo, "create_message", mock_create_message)

    # Mock agent astream_events dưới dạng async generator
    async def mock_astream_events(*args, **kwargs):
        yield {"event": "on_chain_end", "data": {"output": {"response": "Tôi là Trợ lý AI Phân tích Học tập."}}}

    monkeypatch.setattr(agent, "astream_events", mock_astream_events)

    # Gửi request chat trong session cũ
    response = await test_client.post(
        "/api/v1/chat", json={"message": "hãy giới thiệu về bạn", "session_id": str(session_id)}
    )

    assert response.status_code == 200

    # Parse SSE events từ stream text
    content = response.text
    lines = content.strip().split("\n\n")
    events = []
    for line in lines:
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    session_id_event = next(e for e in events if e["type"] == "session_id")
    token_events = [e["content"] for e in events if e["type"] == "token"]
    ai_response = "".join(token_events)

    assert session_id_event["content"] == str(session_id)
    assert ai_response == "Tôi là Trợ lý AI Phân tích Học tập."
    # Chắc chắn rằng không bị lặp lại tin nhắn AI cũ ("Top student is Nguyen Van A")
    assert ai_response != "Top student is Nguyen Van A"
