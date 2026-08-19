"""Worker hàng chờ nạp sách giáo khoa (DB-backed FIFO).

Pattern nhân bản từ src/ews/job_worker.py:
  1. Quét dọn job 'processing' quá 5 phút chưa xong -> 'failed'.
  2. Nếu có job 'processing' đang chạy -> hoãn (chỉ chạy 1 job tại một thời điểm).
  3. Lấy job 'pending' cũ nhất -> 'processing' -> đọc file tạm -> ingest_book ->
     'completed' (lưu result_json) -> đệ quy xử lý tiếp.

Kết quả được cập nhật vào bảng curriculum_ingest_jobs; giao diện admin poll để hiển thị.
Chạy qua FastAPI BackgroundTasks (sau POST /curriculum/ingest-book) và khi khởi động app.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.models.tables import CurriculumIngestJob
from src.services import curriculum_ingest
from src.services.curriculum_catalog import get_or_create_book

logger = logging.getLogger(__name__)

# Nạp PDF giờ quét TOÀN BỘ cuốn (VLM) + làm giàu từng bài — cần thời gian lớn hơn trước.
_TIMEOUT_MINUTES = 60


def process_next_curriculum_ingest_job() -> None:
    """Xử lý 1 job nạp sách pending (nếu có) theo FIFO. Không raise ra ngoài."""
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        # 1. Quét timeout chống kẹt hàng chờ
        timeout_ago = datetime.utcnow() - timedelta(minutes=_TIMEOUT_MINUTES)
        stuck = (
            db.query(CurriculumIngestJob)
            .filter(CurriculumIngestJob.status == "processing", CurriculumIngestJob.started_at < timeout_ago)
            .all()
        )
        for job in stuck:
            job.status = "failed"
            job.error_message = "Quá thời gian xử lý (timeout 5 phút). Vui lòng thử lại."
            job.finished_at = datetime.utcnow()
            logger.warning("Curriculum ingest job %s timed out. Marked as failed.", job.id)
        if stuck:
            db.commit()

        # 2. Kiểm tra job đang chạy (chỉ chạy 1 job tại một thời điểm)
        active = db.query(CurriculumIngestJob).filter(CurriculumIngestJob.status == "processing").first()
        if active:
            logger.info("Curriculum ingest job %s đang chạy. Giữ hàng chờ.", active.id)
            return

        # 3. Lấy job pending cũ nhất
        next_job = (
            db.query(CurriculumIngestJob)
            .filter(CurriculumIngestJob.status == "pending")
            .order_by(CurriculumIngestJob.created_at.asc())
            .first()
        )
        if next_job is None:
            logger.info("Không có curriculum ingest job nào đang đợi.")
            return

        # Chuyển sang processing
        next_job.status = "processing"
        next_job.progress = 5
        next_job.started_at = datetime.utcnow()
        db.commit()
        db.refresh(next_job)

        logger.info(
            "Bắt đầu curriculum ingest job %s: %s khối %d (dry_run=%s)",
            next_job.id,
            next_job.subject_code,
            next_job.grade_number,
            next_job.dry_run,
        )

        try:
            source_file = Path(next_job.source_filepath) if next_job.source_filepath else None
            if source_file is None or not source_file.exists():
                raise ValueError("File tạm nạp sách đã bị mất — cần nạp lại.")
            content = source_file.read_bytes()

            def _progress(done: int, total: int, stage: str) -> None:
                """Cập nhật job.progress theo giai đoạn (scan 10-70, enrich 70-95) — commit để UI poll thấy."""
                if total <= 0:
                    base = 70 if stage == "scan" else 95
                else:
                    ratio = done / total
                    base = 10 + int(60 * ratio) if stage == "scan" else 70 + int(25 * ratio)
                next_job.progress = min(99, base)
                db.commit()

            book_id = None
            if not next_job.dry_run:
                book_id = get_or_create_book(
                    db,
                    next_job.subject_code,
                    next_job.grade_number,
                    next_job.semester_number,
                    next_job.book_title or "",
                    filename=next_job.filename,
                    created_by=next_job.requested_by,
                )

            result = curriculum_ingest.ingest_book(
                db=db,
                filename=next_job.filename or "book.pdf",
                content=content,
                subject_code=next_job.subject_code,
                grade=next_job.grade_number,
                semester=next_job.semester_number,
                include_lessons=next_job.include_lessons,
                dry_run=next_job.dry_run,
                book_id=book_id,
                enrich=next_job.enrich,
                progress_cb=_progress,
            )
            next_job.result_json = json.dumps(result, ensure_ascii=False)
            next_job.status = "completed"
            next_job.progress = 100
            next_job.inserted = result.get("inserted", 0)
            next_job.updated = result.get("updated", 0)
            next_job.hidden_placeholders = result.get("hidden_placeholders", 0)
            next_job.finished_at = datetime.utcnow()
            db.commit()

            # Nạp thẳng (dry_run=false, không qua /commit): lưu file PDF gốc để render ảnh bìa
            if not next_job.dry_run and book_id is not None and source_file is not None:
                try:
                    from src.api.v1.curriculum import _BOOK_DIR, _book_pdf_path

                    _BOOK_DIR.mkdir(parents=True, exist_ok=True)
                    _book_pdf_path(book_id).write_bytes(source_file.read_bytes())
                    source_file.unlink(missing_ok=True)
                except (OSError, ImportError) as exc:  # noqa: BLE001
                    logger.warning("Không lưu được file gốc cuốn %s: %s", book_id, exc)
            logger.info("Curriculum ingest job %s hoàn tất: %d chương", next_job.id, len(result.get("chapters", [])))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Curriculum ingest job %s thất bại", next_job.id)
            next_job.status = "failed"
            next_job.error_message = str(exc)[:2000]
            next_job.finished_at = datetime.utcnow()
            db.commit()
        # KHÔNG xóa file tạm ở đây — commit (/ingest-book/commit) cần file PDF gốc để lưu
        # vào uploads/curriculum_books/{book_id}.pdf (render ảnh bìa). Commit tự dọn sau khi copy.

        # Xử lý job pending tiếp theo (nếu có)
        process_next_curriculum_ingest_job()
    except Exception as exc:  # noqa: BLE001
        logger.error("Lỗi trong quá trình xử lý hàng chờ curriculum ingest: %s", exc)
    finally:
        db.close()
