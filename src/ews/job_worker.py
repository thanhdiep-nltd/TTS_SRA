# -*- coding: utf-8 -*-
"""
src/ews/job_worker.py — Worker xử lý hàng chờ dự đoán EWS (BGH control panel).

Pattern DB-backed FIFO (giống process_next_vms_task trong recordings.py):
  1. Quét dọn job 'processing' quá 5 phút chưa xong -> 'failed'.
  2. Nếu có job 'processing' đang chạy -> hoãn (chỉ chạy 1 job tại một thời điểm).
  3. Lấy job 'pending' cũ nhất -> 'processing' -> chạy run_pipeline (theo trường,
     dùng config đã merge override) -> 'completed' -> đệ quy xử lý tiếp.

Kết quả được cập nhật vào bảng ews_pipeline_jobs; giao diện BGH poll để hiển thị.
Chạy qua FastAPI BackgroundTasks (sau POST /ews/predict) và khi khởi động app.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.ews.ews_config_service import get_effective_config
from src.ews.pipeline_runner import run_pipeline
from src.models.tables import EwsPipelineJob

logger = logging.getLogger(__name__)

_TIMEOUT_MINUTES = 5


def process_next_ews_job() -> None:
    """Xử lý 1 job EWS pending (nếu có) theo FIFO. Không raise ra ngoài."""
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        # 1. Quét timeout chống kẹt hàng chờ
        timeout_ago = datetime.utcnow() - timedelta(minutes=_TIMEOUT_MINUTES)
        stuck = (
            db.query(EwsPipelineJob)
            .filter(
                EwsPipelineJob.status == "processing",
                EwsPipelineJob.started_at < timeout_ago,
            )
            .all()
        )
        for job in stuck:
            job.status = "failed"
            job.error_message = "Quá thời gian xử lý (timeout 5 phút). Vui lòng thử lại."
            job.finished_at = datetime.utcnow()
            logger.warning("EWS job %s timed out. Marked as failed.", job.id)
        if stuck:
            db.commit()

        # 2. Kiểm tra job đang chạy
        active = (
            db.query(EwsPipelineJob)
            .filter(EwsPipelineJob.status == "processing")
            .first()
        )
        if active:
            logger.info("EWS job %s đang chạy. Giữ hàng chờ.", active.id)
            return

        # 3. Lấy job pending cũ nhất
        next_job = (
            db.query(EwsPipelineJob)
            .filter(EwsPipelineJob.status == "pending")
            .order_by(EwsPipelineJob.created_at.asc())
            .first()
        )
        if next_job is None:
            logger.info("Không có EWS job nào đang đợi.")
            return

        # Chuyển sang processing
        next_job.status = "processing"
        next_job.progress = 5
        next_job.started_at = datetime.utcnow()
        db.commit()
        db.refresh(next_job)

        logger.info(
            "Bắt đầu EWS job %s: school=%d, year=%d, sem=%d, week=%d, model=%s",
            next_job.id, next_job.so_school_id, next_job.school_year_id,
            next_job.semester_index, next_job.evaluated_at_week, next_job.model_version,
        )

        try:
            # Config hiệu lực theo trường (baseline + override) — chỉ dùng cho v2_ensemble
            cfg = get_effective_config(db, next_job.so_school_id)
            result = run_pipeline(
                session=db,
                school_year_id=next_job.school_year_id,
                semester_index=next_job.semester_index,
                evaluated_at_week=next_job.evaluated_at_week,
                cutoff_date=next_job.cutoff_date,
                skip_shap=False,  # Bật SHAP drivers (Top 5 nhân tố tác động AI)
                model_version=next_job.model_version,
                so_school_id=next_job.so_school_id,
                cfg=cfg,
                enable_llm=True,
            )
            next_job.status = "completed"
            next_job.progress = 100
            next_job.rows_processed = len(result)
            next_job.finished_at = datetime.utcnow()
            db.commit()
            logger.info("EWS job %s hoàn tất: %d dòng", next_job.id, len(result))
        except Exception as exc:  # noqa: BLE001
            logger.exception("EWS job %s thất bại", next_job.id)
            next_job.status = "failed"
            next_job.error_message = str(exc)[:2000]
            next_job.finished_at = datetime.utcnow()
            db.commit()

        # Xử lý job pending tiếp theo (nếu có)
        process_next_ews_job()
    except Exception as exc:  # noqa: BLE001
        logger.error("Lỗi trong quá trình xử lý hàng chờ EWS: %s", exc)
    finally:
        db.close()
