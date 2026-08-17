"""Script ingest giáo án từ 7 bảng s360.cm_* vào Qdrant collection `edu_knowledge`.

Đọc dữ liệu phân cấp: cm_course -> cm_unit -> cm_lesson -> cm_lessonplan + cm_lessontarget,
tạo embedding và upsert vào Qdrant với metadata `source="giao_an"`.
Chạy độc lập: `PYTHONPATH=. python scripts/ingest_lesson_plans.py`
"""

import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db.session import SessionLocal  # noqa: E402
from src.services import retrieval  # noqa: E402


def _mon_to_slug(subject_id: int | None, course_name: str | None) -> str:
    name = (course_name or "").lower()
    if "toán" in name or "toan" in name:
        return "toan"
    if "khoa học tự nhiên" in name or "khtn" in name:
        return "khoa_hoc_tu_nhien"
    if "văn" in name or "ngữ văn" in name:
        return "ngu_van"
    if "lý" in name or "vật lí" in name or "vật lý" in name:
        return "vat_ly"
    if "hóa" in name:
        return "hoa_hoc"
    if "sinh" in name:
        return "sinh_hoc"
    if "sử" in name or "lịch sử" in name:
        return "lich_su"
    if "địa" in name:
        return "dia_ly"
    return "chung"


def ingest_lesson_plans() -> None:
    settings = get_settings()
    db = SessionLocal()

    print("[INFO] Bắt đầu truy vấn dữ liệu giáo án từ s360.cm_*...")
    query = text("""
        SELECT
            lp.id AS lessonplan_id,
            lp.name AS lessonplan_name,
            lp.content_own,
            lp.description AS lp_description,
            l.id AS lesson_id,
            l.name AS lesson_name,
            l.description AS lesson_description,
            u.id AS unit_id,
            u.name AS unit_name,
            c.id AS course_id,
            c.name AS course_name,
            c.subject_id,
            c.grade_id,
            COALESCE(
                (SELECT string_agg(lt.name || ': ' || COALESCE(lt.description, ''), '; ')
                 FROM s360.cm_lessontarget lt
                 WHERE lt.lesson_id = l.id AND lt.is_deleted = FALSE),
                ''
            ) AS targets
        FROM s360.cm_lessonplan lp
        JOIN s360.cm_lesson l ON l.id = lp.lesson_id AND l.is_deleted = FALSE
        JOIN s360.cm_unit u ON u.id = l.unit_id AND u.is_deleted = FALSE
        JOIN s360.cm_course c ON c.id = u.course_id AND c.is_deleted = FALSE
        WHERE lp.is_deleted = FALSE
        ORDER BY lp.id
    """)

    try:
        rows = db.execute(query).fetchall()
    except Exception as exc:
        print(f"[WARN] Không thể đọc bảng s360.cm_* (có thể bảng chưa có data hoặc chưa tạo): {exc}")
        db.close()
        return

    print(f"[INFO] Tìm thấy {len(rows)} bản ghi giáo án.")
    if not rows:
        print("[INFO] Không có bản ghi giáo án nào cần ingest.")
        db.close()
        return

    points = []
    for r in rows:
        mon_slug = _mon_to_slug(r.subject_id, r.course_name)
        grade_str = str(r.grade_id) if r.grade_id else "0"

        content_parts = []
        if r.course_name:
            content_parts.append(f"Môn học: {r.course_name}")
        if r.grade_id:
            content_parts.append(f"Khối: {r.grade_id}")
        if r.unit_name:
            content_parts.append(f"Chương/Bài lớn: {r.unit_name}")
        if r.lesson_name:
            content_parts.append(f"Bài học: {r.lesson_name}")
        if r.targets:
            content_parts.append(f"Mục tiêu cần đạt: {r.targets}")
        if r.content_own:
            content_parts.append(f"Nội dung giáo án: {r.content_own}")
        elif r.lp_description or r.lesson_description:
            content_parts.append(f"Mô tả: {r.lp_description or r.lesson_description}")

        doc_text = "\n".join(content_parts)
        if len(doc_text.strip()) < 20:
            continue

        try:
            vec = retrieval.embed_query(doc_text[:2000], settings)
        except Exception as embed_err:
            print(f"[WARN] Lỗi embed giáo án #{r.lessonplan_id}: {embed_err}")
            continue

        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"giao_an_{r.lessonplan_id}"))
        points.append({
            "id": point_id,
            "vector": vec,
            "payload": {
                "source": "giao_an",
                "mon": mon_slug,
                "lop": grade_str,
                "chuong": r.unit_name,
                "heading": r.lesson_name or r.lessonplan_name,
                "unit_name": r.unit_name,
                "lesson_name": r.lesson_name,
                "subject_id": r.subject_id,
                "grade_id": r.grade_id,
                "lessonplan_id": r.lessonplan_id,
                "text": doc_text,
            },
        })

    if not points:
        print("[INFO] Không có vector nào được tạo.")
        db.close()
        return

    print(f"[INFO] Đang nạp {len(points)} vector vào Qdrant collection `{settings.qdrant_collection}`...")
    headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        resp = httpx.put(
            f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points",
            json={"points": batch},
            headers=headers,
            timeout=settings.retrieval_timeout_s * 2,
        )
        resp.raise_for_status()
        print(f"  -> Đã nạp batch {i + 1} - {min(i + batch_size, len(points))}")

    print("[SUCCESS] Hoàn thành ingest giáo án vào Qdrant!")
    db.close()


if __name__ == "__main__":
    ingest_lesson_plans()
