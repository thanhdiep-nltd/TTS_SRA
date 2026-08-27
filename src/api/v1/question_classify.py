"""API công cụ test 1 câu hỏi (tab "Kiểm tra câu hỏi" trong trang TEVI) — không trạng thái.

POST /exam-difficulty/classify-question: nhận 1 ảnh/PDF (hoặc ảnh dán Ctrl+V) + môn/khối →
VLM đọc text → LLM map vào cây chương/bài SGK đã nạp → trả chương/bài câu hỏi thuộc về.
Không ghi gì vào DB; file tạm bị xóa sau khi xử lý.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models.enums import FileType
from src.schemas.question_classify import QuestionClassifyResult
from src.services import question_classify, storage, vlm

router = APIRouter(prefix="/exam-difficulty", tags=["Exam Difficulty (test câu hỏi)"])


@router.post("/classify-question", response_model=QuestionClassifyResult)
def classify_question(
    subject_code: Annotated[str, Form()],
    grade_number: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    semester_number: Annotated[int | None, Form()] = None,
    vlm_model: Annotated[str | None, Form()] = None,
    user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Đọc 1 câu hỏi (ảnh/PDF/dán ảnh) và xác định thuộc chương/bài nào của SGK đã nạp.

    - 400: file thiếu/định dạng không hỗ trợ (kể cả DOC/DOCX — chỉ ảnh hoặc PDF).
    - 422: môn/khối chưa có trong danh mục hoặc chưa nạp SGK.
    - 503: VLM lỗi/quá tải (message thân thiện từ VlmUnavailableError).
    """
    try:
        stored, _, file_type = storage.save_exam_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if file_type == FileType.WORD:
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ ảnh hoặc PDF cho câu hỏi đơn.")
        try:
            if semester_number is not None:
                shortlist = question_classify.resolve_shortlist(db, subject_code, grade_number, semester_number)
            else:
                shortlist = question_classify.resolve_shortlist(db, subject_code, grade_number)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            text = question_classify.extract_question_text(
                storage.exam_file_path(stored), file_type, vlm_model=vlm_model
            )
        except vlm.VlmUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        subject_id = shortlist[0].subject_id if shortlist else None
        return question_classify.classify_question(
            text,
            shortlist,
            db=db,
            subject_id=subject_id,
            grade_number=grade_number,
        )
    finally:
        storage.delete_exam_file(stored)
