import asyncio
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.routes import router
from src.api.v1 import api_router
from src.config import get_settings
from src.observability import setup_observability
from src.services.observability_snapshot import run_snapshot_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")

    # Auto-create missing helper tables (e.g. ai_observability_snapshots)
    try:
        import src.models.tables  # noqa: F401
        from src.db.base import Base
        from src.db.session import engine
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        print(f"Table creation check: {exc}")

    # Startup Self-Healing for stuck camera tasks
    if settings.app_env != "test" and "pytest" not in sys.modules:
        try:
            from src.api.v1.recordings import process_next_vms_task
            from src.db.session import SessionLocal
            from src.models.tables import ClassroomRecording

            db = SessionLocal()
            stuck = (
                db.query(ClassroomRecording)
                .filter(
                    ClassroomRecording.status == "processing",
                    ClassroomRecording.audio_file_url == "vms_extraction_pending",
                )
                .all()
            )
            if stuck:
                print(f"Startup Self-Healing: Đánh dấu {len(stuck)} task trích xuất camera kẹt thành 'failed'...")
                for task in stuck:
                    task.status = "failed"
                    task.progress = 0
                    task.ai_report = "### LỖI KHỞI ĐỘNG HỆ THỐNG\n- Tiến trình trích xuất camera bị gián đoạn do hệ thống khởi động lại.\n- Vui lòng thử bấm 'Thử lại' hoặc 'Xóa bỏ' để giải phóng hàng chờ."
                db.commit()
            db.close()
            # Khởi chạy hàng chờ để xử lý task pending khác (nếu có)
            process_next_vms_task()
        except Exception as e:
            print(f"Startup Self-Healing Error: {e}")

        # Startup Self-Healing cho hàng chờ dự đoán EWS (BGH control panel)
        try:
            from src.db.session import SessionLocal
            from src.ews.job_worker import process_next_ews_job
            from src.models.tables import EwsPipelineJob

            db = SessionLocal()
            stuck = (
                db.query(EwsPipelineJob)
                .filter(EwsPipelineJob.status == "processing")
                .all()
            )
            if stuck:
                print(f"Startup Self-Healing: Đánh dấu {len(stuck)} EWS job kẹt thành 'failed'...")
                for job in stuck:
                    job.status = "failed"
                    job.error_message = "Bị gián đoạn do hệ thống khởi động lại. Vui lòng thử lại."
                    job.finished_at = datetime.utcnow()
                db.commit()
            db.close()
            # Khởi chạy hàng chờ EWS để xử lý job pending (nếu có)
            process_next_ews_job()
        except Exception as e:
            print(f"Startup EWS Self-Healing Error: {e}")

        # Startup Self-Healing cho hàng chờ nạp sách giáo khoa (DB-backed queue)
        try:
            from src.db.session import SessionLocal
            from src.models.tables import CurriculumIngestJob
            from src.services.curriculum_job_worker import process_next_curriculum_ingest_job

            db = SessionLocal()
            stuck = db.query(CurriculumIngestJob).filter(CurriculumIngestJob.status == "processing").all()
            if stuck:
                print(f"Startup Self-Healing: Đánh dấu {len(stuck)} job nạp sách kẹt thành 'failed'...")
                for job in stuck:
                    job.status = "failed"
                    job.error_message = "Bị gián đoạn do hệ thống khởi động lại. Vui lòng thử lại."
                    job.finished_at = datetime.utcnow()
                db.commit()
            db.close()
            # Khởi chạy hàng chờ để xử lý job pending (nếu có)
            process_next_curriculum_ingest_job()
        except Exception as e:
            print(f"Startup Curriculum Ingest Self-Healing Error: {e}")

    # Snapshot job cho trend chart "Tình trạng hệ thống AI" (ẩn khi chạy test)

    snapshot_task = None
    if settings.app_env != "test" and "pytest" not in sys.modules:
        # Stack Grafana/Prometheus (docker-compose) chỉ chạy khi dev local có Docker Desktop.
        # KHÔNG tự khởi động ở production (Railway chỉ có 1 container, không có docker-compose).
        if settings.app_env != "production":
            try:
                print("Auto-starting docker-compose observability stack...")
                subprocess.Popen(["docker-compose", "up", "-d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Warning: Failed to auto-start docker-compose: {e}. Is Docker Desktop running?")

        snapshot_task = asyncio.create_task(run_snapshot_loop())

    yield

    if snapshot_task:
        snapshot_task.cancel()
    print("Shutting down...")


settings = get_settings()

app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_observability(app)


# Message tiếng Việt cụ thể theo tên constraint (SQLAlchemy naming convention ở src/db/base.py),
# để người dùng biết chính xác mình trùng/sai cái gì thay vì 1 câu chung chung "vi phạm ràng buộc".
_CONSTRAINT_MESSAGES: dict[str, str] = {
    "uq_users_email": "Email này đã được sử dụng bởi tài khoản khác.",
    "uq_schools_code": "Mã trường này đã tồn tại.",
    "uq_academic_year_school_name": "Niên khóa này đã tồn tại trong trường.",
    "uq_semester_year_number": "Học kỳ này đã tồn tại trong niên khóa.",
    "uq_grade_school_number": "Khối này đã tồn tại trong trường.",
    "uq_class_grade_name_year": "Lớp này đã tồn tại trong khối/niên khóa.",
    "uq_subject_school_code": "Mã môn học này đã tồn tại trong trường.",
    "uq_student_school_code": "Mã học sinh này đã tồn tại trong trường.",
    "uq_enrollment_student_year": "Học sinh đã được ghi danh trong niên khóa này.",
    "uq_curriculum_subject_grade_code": "Mã đơn vị kiến thức này đã tồn tại cho môn/khối.",
    "uq_teacher_assignment": "Phân công giảng dạy này đã tồn tại (trùng vai trò/lớp/khối/môn/niên khóa).",
    "uq_score_unique": "Điểm cho cột này đã tồn tại — hãy sửa điểm hiện có thay vì tạo mới.",
}

_SQLSTATE_FALLBACK: dict[str, str] = {
    "23505": "Dữ liệu bị trùng lặp (vi phạm ràng buộc duy nhất).",
    "23503": "Tham chiếu đến dữ liệu không tồn tại (khóa ngoại không hợp lệ).",
    "23514": "Giá trị không hợp lệ (vi phạm ràng buộc kiểm tra).",
}


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Ràng buộc DB bị vi phạm (trùng unique, sai FK, vi phạm CHECK) -> 409.

    `diag` (psycopg) cho tên constraint + sqlstate chính xác -> trả message cụ thể thay vì
    1 câu gộp chung, giúp người nhập biết ngay mình trùng/sai cái gì.
    """
    diag = getattr(getattr(exc, "orig", None), "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    sqlstate = getattr(diag, "sqlstate", None)

    detail = (
        _CONSTRAINT_MESSAGES.get(constraint_name)
        or _SQLSTATE_FALLBACK.get(sqlstate)
        or "Ràng buộc dữ liệu bị vi phạm (trùng lặp, khóa ngoại không tồn tại, hoặc giá trị không hợp lệ)."
    )
    return JSONResponse(status_code=409, content={"detail": detail})


app.include_router(router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "db": db_ok, "env": settings.app_env}
