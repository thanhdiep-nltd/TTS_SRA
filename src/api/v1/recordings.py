import logging
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.config import get_settings
from src.models import enums
from src.models.tables import Class, ClassroomRecording, Subject, User
from src.schemas.recording import (
    CameraExtractRequest,
    CameraWebhookPayload,
    ClassroomRecordingList,
    ClassroomRecordingRead,
)
from src.services import rbac, storage
from src.services.recording_analysis import analyze_recording_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recordings", tags=["Classroom Recordings"])


@router.post("", response_model=ClassroomRecordingRead, status_code=201)
def upload_recording(
    user: CurrentUser,
    subject_id: Annotated[UUID, Form()],
    class_id: Annotated[UUID, Form()],
    semester_id: Annotated[UUID, Form()],
    lesson_name: Annotated[str, Form()],
    period: Annotated[int, Form()],
    date: Annotated[date, Form()],
    week: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Tải lên file ghi âm bài giảng (MP3/WAV/M4A) lên Supabase Storage và kích hoạt phân tích nền AI."""
    # Kiểm tra phân quyền upload (Giáo viên phải được phân công lớp+môn này)
    if not rbac.can_write_score(db, user, subject_id, class_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền nộp ghi âm bài giảng cho môn học và lớp học này.",
        )

    # Đẩy file lên Cloud Storage
    try:
        audio_url = storage.save_recording_to_cloud(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Tạo bản ghi trong database
    recording = ClassroomRecording(
        school_id=user.school_id,
        teacher_id=user.id,
        subject_id=subject_id,
        class_id=class_id,
        semester_id=semester_id,
        lesson_name=lesson_name,
        period=period,
        date=date,
        week=week,
        audio_file_url=audio_url,
        status="pending",
        progress=0,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    # Điền tên hiển thị cho response model
    recording.teacher_name = user.full_name
    subj = db.get(Subject, subject_id)
    recording.subject_name = subj.name if subj else None
    kls = db.get(Class, class_id)
    recording.class_name = kls.name if kls else None

    # Kích hoạt Background task chạy WhisperX + LLM
    background_tasks.add_task(analyze_recording_background, recording.id)

    return recording


@router.get("", response_model=list[ClassroomRecordingList])
def list_recordings(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Lấy danh sách các ghi âm tiết dạy.
    - BGH (ADMIN/PRINCIPAL): xem toàn bộ ghi âm của trường.
    - Giáo viên: Chỉ xem ghi âm của chính mình, ẩn các trường nhạy cảm liên quan tới AI.
    """
    is_bgh = user.role in {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}

    stmt = (
        select(
            ClassroomRecording,
            User.full_name.label("teacher_name"),
            Subject.name.label("subject_name"),
            Class.name.label("class_name"),
        )
        .join(User, ClassroomRecording.teacher_id == User.id)
        .join(Subject, ClassroomRecording.subject_id == Subject.id)
        .join(Class, ClassroomRecording.class_id == Class.id)
        .where(ClassroomRecording.so_school_id == user.so_school_id)
    )

    if not is_bgh:
        # Hạn chế giáo viên chỉ xem bản ghi của chính họ
        stmt = stmt.where(ClassroomRecording.teacher_id == user.id)

    rows = db.execute(stmt.order_by(ClassroomRecording.created_at.desc())).all()
    recordings = []

    for rec, teacher_name, subject_name, class_name in rows:
        rec.teacher_name = teacher_name
        rec.subject_name = subject_name
        rec.class_name = class_name

        # Ẩn các trường kết quả AI đối với giáo viên (chỉ BGH mới được xem)
        if not is_bgh:
            rec.score = None
            rec.engagement = None
            rec.rank = None

        recordings.append(rec)

    return recordings


@router.get("/{recording_id}", response_model=ClassroomRecordingRead)
def get_recording(
    recording_id: UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Xem báo cáo chi tiết đánh giá ghi âm bài giảng (chỉ dành cho BGH)."""
    is_bgh = user.role in {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}
    if not is_bgh:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền truy cập kết quả đánh giá sư phạm của bài dạy này.",
        )

    row = db.execute(
        select(
            ClassroomRecording,
            User.full_name.label("teacher_name"),
            Subject.name.label("subject_name"),
            Class.name.label("class_name"),
        )
        .join(User, ClassroomRecording.teacher_id == User.id)
        .join(Subject, ClassroomRecording.subject_id == Subject.id)
        .join(Class, ClassroomRecording.class_id == Class.id)
        .where(ClassroomRecording.id == recording_id)
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi âm bài dạy")

    recording, teacher_name, subject_name, class_name = row

    if recording.school_id != user.school_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập bản ghi âm này")

    # Gán các tên liên quan cho schema đọc
    recording.teacher_name = teacher_name
    recording.subject_name = subject_name
    recording.class_name = class_name

    # Sinh Signed URL động nếu có file âm thanh
    if recording.audio_file_url and recording.audio_file_url != "vms_extraction_pending":
        url_parts = recording.audio_file_url.split("/")
        filename = url_parts[-1].split("?")[0]
        bucket = url_parts[-2] if len(url_parts) >= 2 and url_parts[-2] in {"audios", "videos", "lectures"} else None
        try:
            recording.audio_file_url = storage.generate_signed_audio_url(filename, expires_in=3600, bucket=bucket)
        except Exception as e:
            logger.error(f"Lỗi tạo Signed URL động cho file {filename} trong bucket {bucket}: {e}")

    return recording


@router.post("/{recording_id}/analyze", status_code=202)
def trigger_recording_analyze(
    recording_id: UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Kích hoạt lại tiến trình phân tích AI thủ công (khi trạng thái cũ bị failed hoặc cần phân tích lại)."""
    recording = db.get(ClassroomRecording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi âm bài dạy")

    if recording.school_id != user.school_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập bản ghi âm này")

    is_bgh = user.role in {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}
    if not is_bgh and recording.teacher_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền yêu cầu phân tích bản ghi âm của giáo viên khác.",
        )

    # Nếu là bản ghi từ Camera và chưa trích xuất được âm thanh (VMS chưa xong hoặc lỗi kết nối VMS)
    if recording.audio_file_url == "vms_extraction_pending":
        recording.status = "pending"
        recording.progress = 0
        recording.ai_report = None
        db.commit()
        db.refresh(recording)
        background_tasks.add_task(process_next_vms_task)
        return {"status": "queued", "type": "camera"}
    else:
        background_tasks.add_task(analyze_recording_background, recording.id)
        return {"status": "queued", "type": "upload"}


@router.delete("/{recording_id}", status_code=204)
def delete_recording(
    recording_id: UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Xóa bản ghi âm bài dạy (xóa cả trên DB và trên Cloud Storage)."""
    recording = db.get(ClassroomRecording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi âm bài dạy")

    if recording.school_id != user.school_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập bản ghi âm này")

    is_bgh = user.role in {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}
    if not is_bgh and recording.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa bản ghi âm này.")

    # Xóa file trên Supabase Cloud Storage
    try:
        storage.delete_recording_from_cloud(recording.audio_file_url)
    except Exception as exc:
        logger.warning("Không thể xóa file ghi âm trên Cloud: %s", exc)

    db.delete(recording)
    db.commit()


def process_next_vms_task():
    """Quản lý hàng chờ DB-backed FIFO:
    1. Quét dọn các task 'processing' quá 5 phút mà chưa xong -> Đánh dấu 'failed'.
    2. Kiểm tra xem có task nào đang chạy ('processing') không. Nếu có, hoãn xử lý task khác.
    3. Nếu không có task nào chạy, lấy task 'pending' cũ nhất và gửi lệnh sang VMS_DEMO.
    """
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        settings = get_settings()

        # 1. Quét timeout 5 phút chống kẹt hàng chờ
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        stuck_tasks = (
            db.query(ClassroomRecording)
            .filter(
                ClassroomRecording.status == "processing",
                ClassroomRecording.audio_file_url == "vms_extraction_pending",
                ClassroomRecording.updated_at < five_minutes_ago,
            )
            .all()
        )

        for task in stuck_tasks:
            task.status = "failed"
            task.ai_report = "### LỖI HỆ THỐNG\n- Quá thời gian trích xuất âm thanh từ VMS_DEMO (Timeout 5 phút).\n- Vui lòng thử bấm 'Đánh giá lại AI'."
            logger.warning(f"VMS Task {task.id} timed out. Marked as failed.")
        if stuck_tasks:
            db.commit()

        # 2. Kiểm tra xem có task nào đang chạy không
        active_task = (
            db.query(ClassroomRecording)
            .filter(
                ClassroomRecording.status == "processing", ClassroomRecording.audio_file_url == "vms_extraction_pending"
            )
            .first()
        )

        if active_task:
            logger.info(f"VMS_DEMO đang bận xử lý task {active_task.id}. Giữ hàng chờ.")
            return

        # 3. Lấy task pending cũ nhất ra gửi sang VMS_DEMO
        next_task = (
            db.query(ClassroomRecording)
            .filter(
                ClassroomRecording.status == "pending", ClassroomRecording.audio_file_url == "vms_extraction_pending"
            )
            .order_by(ClassroomRecording.created_at.asc())
            .first()
        )

        if not next_task:
            logger.info("Không có task VMS nào đang đợi.")
            return

        # Chuyển trạng thái sang processing
        next_task.status = "processing"
        next_task.progress = 10
        db.commit()
        db.refresh(next_task)

        # Lấy thông tin lớp học và tiết học
        klass = db.get(Class, next_task.class_id)
        class_name = klass.name if klass else "7A1"

        # Ánh xạ period sang giờ bắt đầu (from)
        # 1 -> 08:00, 2 -> 08:50, 3 -> 09:40, 4 -> 10:30, 5 -> 11:20
        period_map = {1: "08:00", 2: "08:50", 3: "09:40", 4: "10:30", 5: "11:20"}
        from_time = period_map.get(next_task.period, "08:00")

        # Gửi lệnh sang VMS_DEMO
        vms_url = f"{settings.vms_server_url}/api/vms/download-record"
        params = {"cam_id": class_name, "from": from_time, "date": next_task.date.strftime("%Y%m%d")}

        logger.info(f"Gửi lệnh trích xuất camera sang VMS: {vms_url} với params {params}")
        try:
            resp = httpx.get(vms_url, params=params, timeout=5.0)
            if resp.status_code == 200:
                logger.info(f"Gửi yêu cầu trích xuất camera thành công cho task {next_task.id}")
            else:
                logger.error(f"VMS trả về mã lỗi {resp.status_code}: {resp.text}")
                next_task.status = "failed"
                next_task.ai_report = f"### LỖI KẾT NỐI VMS\n- VMS trả về mã lỗi {resp.status_code}"
                db.commit()
                # Gọi đệ quy xử lý task tiếp theo
                process_next_vms_task()
        except Exception as e:
            logger.error(f"Không thể kết nối tới VMS server: {e}")
            next_task.status = "failed"
            next_task.ai_report = f"### LỖI KẾT NỐI VMS\n- Không thể kết nối tới {settings.vms_server_url}: {str(e)}"
            db.commit()
            # Gọi đệ quy xử lý task tiếp theo
            process_next_vms_task()
    except Exception as e:
        logger.error(f"Lỗi trong quá trình xử lý hàng chờ VMS: {e}")
    finally:
        db.close()


@router.post("/camera-extract", response_model=ClassroomRecordingRead, status_code=201)
def camera_extract(
    req: CameraExtractRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Yêu cầu trích xuất dữ liệu camera của một lớp học và tiết học cụ thể."""
    if user.role not in {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện chức năng trích xuất camera.",
        )

    klass = db.get(Class, req.class_id)
    if not klass:
        raise HTTPException(status_code=404, detail="Lớp học không tồn tại.")

    subj = db.get(Subject, req.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Môn học không tồn tại.")

    teacher = db.get(User, req.teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Giáo viên không tồn tại.")

    recording = ClassroomRecording(
        school_id=user.school_id,
        teacher_id=req.teacher_id,
        subject_id=req.subject_id,
        class_id=req.class_id,
        semester_id=req.semester_id,
        lesson_name=req.lesson_name,
        period=req.period,
        date=req.date,
        week=req.week,
        audio_file_url="vms_extraction_pending",
        status="pending",
        progress=0,
    )

    db.add(recording)
    db.commit()
    db.refresh(recording)

    recording.teacher_name = teacher.full_name
    recording.subject_name = subj.name
    recording.class_name = klass.name

    background_tasks.add_task(process_next_vms_task)

    return recording


@router.post("/vms-webhook", status_code=200)
def vms_webhook(
    payload: CameraWebhookPayload,
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Webhook nhận callback từ VMS_DEMO sau khi trích xuất xong âm thanh MP3."""
    logger.info(f"Nhận webhook từ VMS: cam_id={payload.cam_id}, from={payload.from_time}, status={payload.status}")

    time_map = {"08:00": 1, "08:50": 2, "09:40": 3, "10:30": 4, "11:20": 5}
    period = time_map.get(payload.from_time, 1)

    # Khớp nối bản ghi bằng cách JOIN trực tiếp với bảng Class để lọc theo tên lớp (tránh trùng tên lớp giữa các niên khóa khác nhau)
    recording = (
        db.query(ClassroomRecording)
        .join(Class, ClassroomRecording.class_id == Class.id)
        .filter(
            Class.name == payload.cam_id,
            ClassroomRecording.period == period,
            ClassroomRecording.status == "processing",
            ClassroomRecording.audio_file_url == "vms_extraction_pending",
        )
        .order_by(ClassroomRecording.created_at.desc())
        .first()
    )

    if not recording:
        logger.warning("Không tìm thấy bản ghi camera đang chờ tương ứng.")
        return {"status": "ignored", "message": "No matching active extraction task found."}

    if payload.status == "completed":
        recording.audio_file_url = payload.audioUrl
        recording.progress = 30
        db.commit()
        logger.info(f"Cập nhật link MP3 thành công cho task {recording.id}: {payload.audioUrl}")

        background_tasks.add_task(analyze_recording_background, recording.id)
    else:
        recording.status = "failed"
        recording.ai_report = "### LỖI TRÍCH XUẤT CAMERA\n- VMS báo cáo lỗi trích xuất âm thanh."
        db.commit()
        logger.error(f"VMS báo lỗi trích xuất cho task {recording.id}")

    background_tasks.add_task(process_next_vms_task)

    return {"status": "success"}
