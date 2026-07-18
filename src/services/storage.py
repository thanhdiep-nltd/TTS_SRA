"""Lưu trữ file đề thi trên đĩa local. Production nên chuyển sang object storage."""

import pathlib
import uuid

from fastapi import UploadFile

from src.config import get_settings
from src.models.enums import FileType

_EXT_TYPE: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".doc": FileType.WORD,
    ".docx": FileType.WORD,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".png": FileType.IMAGE,
}


def _root() -> pathlib.Path:
    return pathlib.Path(get_settings().upload_dir) / "exams"


def save_exam_file(file: UploadFile) -> tuple[str, int, FileType]:
    """Lưu file đề; trả (tên_lưu, kích_thước_byte, loại_file). Raise ValueError nếu không hợp lệ."""
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in _EXT_TYPE:
        raise ValueError(f"Định dạng không hỗ trợ: {ext or '(không rõ)'}. Cho phép: PDF/DOC/DOCX/ảnh.")
    content = file.file.read()
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"File vượt quá {get_settings().max_upload_mb} MB.")
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    (root / stored).write_bytes(content)
    return stored, len(content), _EXT_TYPE[ext]


def exam_file_path(stored_name: str) -> pathlib.Path:
    return _root() / stored_name


def delete_exam_file(stored_name: str) -> None:
    path = _root() / stored_name
    if path.exists():
        path.unlink()


def _chat_attachment_root() -> pathlib.Path:
    return pathlib.Path(get_settings().upload_dir) / "chat_attachments"


def save_chat_attachment(file: UploadFile) -> tuple[str, int, FileType]:
    """Lưu file đính kèm chat; trả (tên_lưu, kích_thước_byte, loại_file). Raise ValueError nếu không hợp lệ."""
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in _EXT_TYPE:
        raise ValueError(f"Định dạng không hỗ trợ: {ext or '(không rõ)'}. Cho phép: PDF/DOC/DOCX/ảnh.")
    content = file.file.read()
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"File vượt quá {get_settings().max_upload_mb} MB.")
    root = _chat_attachment_root()
    root.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    (root / stored).write_bytes(content)
    return stored, len(content), _EXT_TYPE[ext]


def chat_attachment_path(stored_name: str) -> pathlib.Path:
    return _chat_attachment_root() / stored_name


def delete_chat_attachment(stored_name: str) -> None:
    path = _chat_attachment_root() / stored_name
    if path.exists():
        path.unlink()


# ============================================================
# CLOUD STORAGE FOR CLASSROOM RECORDINGS
# ============================================================

_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def _get_supabase_client():
    from supabase import create_client

    s = get_settings()
    if not s.supabase_url or not s.supabase_key:
        raise ValueError("Cấu hình SUPABASE_URL hoặc SUPABASE_KEY bị thiếu.")
    return create_client(s.supabase_url, s.supabase_key)


def save_recording_to_cloud(file: UploadFile) -> str:
    """Đẩy file ghi âm lên Supabase Storage và trả về public URL."""
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in _AUDIO_EXT:
        raise ValueError(f"Định dạng âm thanh không hỗ trợ: {ext}. Cho phép: MP3/WAV/M4A/AAC/FLAC/OGG.")

    content = file.file.read()
    max_bytes = get_settings().max_upload_mb * 5 * 1024 * 1024  # 100MB max
    if len(content) > max_bytes:
        raise ValueError("File ghi âm vượt quá dung lượng cho phép (100MB).")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    s = get_settings()
    client = _get_supabase_client()

    client.storage.from_(s.supabase_recordings_bucket).upload(
        path=unique_name,
        file=content,
        file_options={"content-type": file.content_type or "audio/mpeg"},
    )

    return client.storage.from_(s.supabase_recordings_bucket).get_public_url(unique_name)


def delete_recording_from_cloud(url: str) -> None:
    """Xóa file ghi âm trên Supabase Storage dựa trên URL."""
    s = get_settings()
    client = _get_supabase_client()
    filename = url.split("/")[-1]
    client.storage.from_(s.supabase_recordings_bucket).remove([filename])


def generate_signed_audio_url(filename: str, expires_in: int = 3600, bucket: str = None) -> str:
    """Sinh Signed URL động thời hạn từ Supabase."""
    s = get_settings()
    client = _get_supabase_client()
    if not bucket:
        if filename.startswith("audio-"):
            bucket = "audios"
        else:
            bucket = s.supabase_recordings_bucket
            
    res = client.storage.from_(bucket).create_signed_url(
        path=filename,
        expires_in=expires_in
    )
    if isinstance(res, dict):
        return res.get("signedURL") or res.get("signedUrl") or ""
    return str(res)
