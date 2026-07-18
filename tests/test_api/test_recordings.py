from datetime import date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user, get_db
from src.main import app
from src.models import enums
from src.models.tables import ClassroomRecording, User

# Mock users
mock_school_id = uuid4()

teacher_user = User(
    id=uuid4(),
    school_id=mock_school_id,
    email="teacher@school.edu.vn",
    full_name="Cô Lê Hoa",
    role=enums.UserRole.SUBJECT_TEACHER,
    is_active=True,
)

bgh_user = User(
    id=uuid4(),
    school_id=mock_school_id,
    email="principal@school.edu.vn",
    full_name="Thầy Hiệu Trưởng",
    role=enums.UserRole.PRINCIPAL,
    is_active=True,
)


def create_mock_recording(teacher_id, lesson_name="Unit 1"):
    return ClassroomRecording(
        id=uuid4(),
        school_id=mock_school_id,
        teacher_id=teacher_id,
        subject_id=uuid4(),
        class_id=uuid4(),
        semester_id=uuid4(),
        lesson_name=lesson_name,
        period=3,
        date=date(2026, 7, 1),
        week=1,
        audio_file_url="https://cloud.supabase/lectures/audio.mp3",
        status="done",
        progress=100,
        score=8.5,
        engagement="85%",
        rank=enums.RecordingRank.EXCELLENT,
        ai_report="### AI Report",
        transcript=[{"time": "00:01", "speaker": "Teacher", "text": "Hello"}],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest_asyncio.fixture
async def test_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_recordings_as_teacher(test_client):
    """Giáo viên chỉ được xem danh sách do họ nộp và kết quả AI bị ẩn (null)."""
    mock_db = MagicMock()
    mock_rec = create_mock_recording(teacher_user.id, "Lesson Teacher")

    # Mock kết quả trả về của DB (gồm ClassroomRecording và tên mock)
    mock_db.execute.return_value.all.return_value = [(mock_rec, teacher_user.full_name, "Tiếng Anh", "Lớp 10A1")]

    # Ghi đè auth và DB
    app.dependency_overrides[get_current_user] = lambda: teacher_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await test_client.get("/api/v1/recordings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["lesson_name"] == "Lesson Teacher"
        assert data[0]["teacher_name"] == teacher_user.full_name

        # Đảm bảo các trường AI nhạy cảm bị ẩn (None/null) đối với giáo viên
        assert data[0]["score"] is None
        assert data[0]["engagement"] is None
        assert data[0]["rank"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_recording_detail_as_teacher_403(test_client):
    """Giáo viên bị cấm xem chi tiết phân tích AI (403 Forbidden)."""
    mock_db = MagicMock()
    mock_rec = create_mock_recording(teacher_user.id)

    # Mock trả về dòng ghi âm
    mock_db.execute.return_value.first.return_value = (mock_rec, teacher_user.full_name, "Tiếng Anh", "Lớp 10A1")

    app.dependency_overrides[get_current_user] = lambda: teacher_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await test_client.get(f"/api/v1/recordings/{mock_rec.id}")
        assert response.status_code == 403
        assert "không có quyền" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_recording_detail_as_bgh_success(test_client):
    """BGH được quyền xem chi tiết và đầy đủ kết quả phân tích AI."""
    mock_db = MagicMock()
    mock_rec = create_mock_recording(teacher_user.id, "Lesson BGH")

    mock_db.execute.return_value.first.return_value = (mock_rec, teacher_user.full_name, "Tiếng Anh", "Lớp 10A1")

    app.dependency_overrides[get_current_user] = lambda: bgh_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = await test_client.get(f"/api/v1/recordings/{mock_rec.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["lesson_name"] == "Lesson BGH"
        assert data["score"] == 8.5
        assert data["engagement"] == "85%"
        assert data["rank"] == "EXCELLENT"
        assert data["ai_report"] == "### AI Report"
        assert len(data["transcript"]) == 1
    finally:
        app.dependency_overrides.clear()
