from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user, get_db
from src.main import app
from src.models import enums
from src.models.tables import AiMessage, AiSession, User
from src.repositories import chat_repo

# Tạo user test cố định
test_user_id = uuid4()
test_user = User(
    id=test_user_id,
    school_id=uuid4(),
    email="teacher_test@school.edu.vn",
    full_name="Giáo Viên Test",
    role=enums.UserRole.SUBJECT_TEACHER,
    is_active=True,
)

test_admin = User(
    id=uuid4(),
    school_id=uuid4(),
    email="admin_test@school.edu.vn",
    full_name="Admin Test",
    role=enums.UserRole.ADMIN,
    is_active=True,
)


@pytest_asyncio.fixture
async def override_deps_teacher():
    """Ghi đè dependencies của FastAPI làm Giáo viên."""
    mock_db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: mock_db
    yield mock_db
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def override_deps_admin():
    """Ghi đè dependencies của FastAPI làm Admin."""
    mock_db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: test_admin
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
async def test_give_message_feedback_success(test_client, override_deps_teacher, monkeypatch):
    """Đánh giá phản hồi thành công (thumbs up/down) bởi chủ sở hữu session."""
    db_mock = override_deps_teacher
    message_id = uuid4()
    session_id = uuid4()

    mock_msg = AiMessage(
        id=message_id,
        session_id=session_id,
        role=enums.AiSessionRole.assistant,
        content="AI Answer Content",
        created_at=datetime.now(),
    )
    mock_session = AiSession(id=session_id, user_id=test_user_id, title="Session Test")

    # Mock db.get
    db_mock.get.side_effect = lambda model, oid: (
        mock_msg if model == AiMessage else (mock_session if model == AiSession else None)
    )

    # Mock update feedback
    def mock_update(db, msg_id, rating, feedback_tag, feedback_text):
        mock_msg.rating = rating
        mock_msg.feedback_tag = feedback_tag
        mock_msg.feedback_text = feedback_text
        mock_msg.feedback_at = datetime.now()
        return mock_msg

    monkeypatch.setattr(chat_repo, "update_message_feedback", mock_update)

    response = await test_client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"rating": -1, "feedback_tag": "Không đúng sự thật", "feedback_text": "Dữ liệu bị sai lệch"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rating"] == -1
    assert data["feedback_tag"] == "Không đúng sự thật"
    assert data["feedback_text"] == "Dữ liệu bị sai lệch"


@pytest.mark.asyncio
async def test_give_message_feedback_validation_khac_required(test_client, override_deps_teacher):
    """Đánh giá thất bại (400 Bad Request) do chọn nhãn 'Khác' nhưng không điền feedback_text."""
    db_mock = override_deps_teacher
    message_id = uuid4()
    session_id = uuid4()

    mock_msg = AiMessage(
        id=message_id,
        session_id=session_id,
        role=enums.AiSessionRole.assistant,
        content="AI Answer Content",
        created_at=datetime.now(),
    )
    mock_session = AiSession(id=session_id, user_id=test_user_id, title="Session Test")
    db_mock.get.side_effect = lambda model, oid: (
        mock_msg if model == AiMessage else (mock_session if model == AiSession else None)
    )

    response = await test_client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        json={"rating": -1, "feedback_tag": "Khác", "feedback_text": "   "},
    )
    assert response.status_code == 400
    assert "Vui lòng nhập ý kiến đóng góp" in response.json()["detail"]


@pytest.mark.asyncio
async def test_give_message_feedback_forbidden(test_client, override_deps_teacher):
    """Đánh giá phản hồi thất bại (403 Forbidden) do không sở hữu session."""
    db_mock = override_deps_teacher
    message_id = uuid4()
    session_id = uuid4()

    mock_msg = AiMessage(
        id=message_id,
        session_id=session_id,
        role=enums.AiSessionRole.assistant,
        content="AI Answer Content",
        created_at=datetime.now(),
    )
    # Lớp session thuộc về user khác
    mock_session = AiSession(id=session_id, user_id=uuid4(), title="Session Test")

    db_mock.get.side_effect = lambda model, oid: (
        mock_msg if model == AiMessage else (mock_session if model == AiSession else None)
    )

    response = await test_client.post(
        f"/api/v1/chat/messages/{message_id}/feedback", json={"rating": -1, "feedback_text": "Báo cáo bị sai lệch"}
    )
    assert response.status_code == 403
    assert "Bạn không có quyền đánh giá" in response.json()["detail"]


@pytest.mark.asyncio
async def test_give_message_feedback_not_found(test_client, override_deps_teacher):
    """Đánh giá phản hồi thất bại (404 Not Found) do tin nhắn không tồn tại."""
    db_mock = override_deps_teacher
    message_id = uuid4()

    db_mock.get.return_value = None

    response = await test_client.post(f"/api/v1/chat/messages/{message_id}/feedback", json={"rating": 1})
    assert response.status_code == 404
    assert "Không tìm thấy tin nhắn" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_admin_telemetry_success(test_client, override_deps_admin):
    """Admin lấy thống kê Telemetry thành công."""
    db_mock = override_deps_admin

    mock_messages = [
        AiMessage(
            id=uuid4(),
            session_id=uuid4(),
            role=enums.AiSessionRole.assistant,
            content="Answer 1",
            rating=1,
            cost=0.00015,
            latency_ms=1500,
            input_token_count=1000,
            output_token_count=200,
            llm_provider="openai",
            model_used="gpt-4o-mini",
            created_at=datetime.now(),
        ),
        AiMessage(
            id=uuid4(),
            session_id=uuid4(),
            role=enums.AiSessionRole.assistant,
            content="Answer 2",
            rating=-1,
            cost=0.00008,
            latency_ms=2500,
            input_token_count=500,
            output_token_count=150,
            llm_provider="deepseek",
            model_used="deepseek-v4-flash",
            created_at=datetime.now(),
        ),
    ]

    # Endpoint giờ chạy 2 query riêng: (1) aggregate qua SQL (SELECT ... .one()),
    # (2) danh sách tin nhắn phân trang (.scalars().all()) — mock lần lượt theo thứ tự gọi.
    agg_row = SimpleNamespace(
        total_requests=2,
        total_errors=0,
        total_cost=0.00023,
        total_latency_ms=4000,
        total_input_tokens=1500,
        total_output_tokens=350,
        total_sessions=2,
        helpful_count=1,
        unhelpful_count=1,
        pii_flagged_count=0,
    )
    agg_result = MagicMock()
    agg_result.one.return_value = agg_row
    msg_result = MagicMock()
    msg_result.scalars.return_value.all.return_value = mock_messages
    db_mock.execute.side_effect = [agg_result, msg_result]

    response = await test_client.get("/api/v1/chat/admin/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cost"] == 0.00023
    assert data["avg_latency_ms"] == 2000.0
    assert data["total_tokens"] == 1850
    assert data["helpful_count"] == 1
    assert data["unhelpful_count"] == 1
    assert len(data["messages"]) == 2


@pytest.mark.asyncio
async def test_get_admin_telemetry_forbidden(test_client, override_deps_teacher):
    """Giáo viên không được truy cập trang admin telemetry (403 Forbidden)."""
    response = await test_client.get("/api/v1/chat/admin/telemetry")
    assert response.status_code == 403
    assert "Bạn không có quyền truy cập" in response.json()["detail"]
