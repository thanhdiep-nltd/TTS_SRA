import uuid

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_import_endpoints_require_auth():
    """Đảm bảo các endpoint import điểm mới được định tuyến đúng và được bảo vệ bởi phân quyền."""
    u = str(uuid.uuid4())

    # 1. GET /scores/import/template
    res_template = client.get(f"/api/v1/scores/import/template?class_id={u}&subject_id={u}&semester_id={u}")
    assert res_template.status_code == 401

    # 2. POST /scores/import/preview
    res_preview = client.post("/api/v1/scores/import/preview", data={"class_id": u, "subject_id": u, "semester_id": u})
    assert res_preview.status_code == 401

    # 3. POST /scores/import/confirm
    res_confirm = client.post(
        "/api/v1/scores/import/confirm", json={"class_id": u, "subject_id": u, "semester_id": u, "records": []}
    )
    assert res_confirm.status_code == 401
