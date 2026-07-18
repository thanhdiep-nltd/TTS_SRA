"""Trích xuất nội dung file đính kèm trong chat để chèn vào prompt cho AI đọc.

Tái dùng `extract_exam_text` (PDF: lớp text + fallback OCR; ảnh: OCR) từ pipeline CDI.
DOCX không được pipeline CDI hỗ trợ (extract_exam_text trả "" cho FileType.WORD) nên
trích riêng bằng python-docx ở đây.
"""

from pathlib import Path

from docx import Document

from src.models.enums import FileType
from src.services.content_difficulty import extract_exam_text


def _extract_docx_text(path: Path) -> str:
    try:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:  # noqa: BLE001 - file hỏng/không đúng định dạng không được crash request
        return ""


def extract_attachment_text(path: Path, file_type: FileType) -> str:
    """Trích text từ file đính kèm (PDF/ảnh tái dùng pipeline CDI, DOCX trích riêng)."""
    if file_type == FileType.WORD:
        return _extract_docx_text(path)
    return extract_exam_text(path, file_type)


def truncate_for_prompt(text: str, max_chars: int) -> tuple[str, bool]:
    """Cắt ngắn nội dung trích xuất nếu vượt `max_chars`. Trả (nội_dung, đã_cắt_hay_không)."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True
