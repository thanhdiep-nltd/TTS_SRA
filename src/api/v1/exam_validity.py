"""Tam giác hóa độ khó đề thi (TEVI) — đối chiếu EDI/CDI để đánh giá độ tin cậy
điểm số toàn trường. Nhạy cảm (liên quan "bê bối") nên chỉ ADMIN/PRINCIPAL/SUBJECT_HEAD
được xem; bảng tổng hợp toàn trường + xếp hạng chỉ ADMIN/PRINCIPAL.

`/student-fairness` (cảnh báo công bằng đánh giá cấp học sinh) nhạy cảm hơn nữa (nhắm vào
GV/HS cụ thể) -> chỉ ADMIN/PRINCIPAL, không cho SUBJECT_HEAD (tránh xung đột lợi ích).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db, require_roles
from src.models.enums import ScoreCategory, UserRole
from src.schemas.exam_validity import ContentAdjustedRankRow, ExamValidityRead, SchoolValidityOverview
from src.schemas.student_fairness import StudentFairnessRow
from src.services import exam_validity, student_fairness

router = APIRouter(prefix="/analytics", tags=["Exam Validity"])

_VALIDITY_READ_ROLES = (UserRole.ADMIN, UserRole.PRINCIPAL, UserRole.SUBJECT_HEAD)
_OVERVIEW_ROLES = (UserRole.ADMIN, UserRole.PRINCIPAL)
_FAIRNESS_ROLES = (UserRole.ADMIN, UserRole.PRINCIPAL)


@router.get(
    "/exam-validity",
    response_model=list[ExamValidityRead],
    dependencies=[Depends(require_roles(*_VALIDITY_READ_ROLES))],
)
def get_exam_validity(
    semester_id: UUID,
    user: CurrentUser,
    subject_id: UUID | None = None,
    score_category: ScoreCategory | None = None,
    grade_id: UUID | None = None,
    flagged_only: bool = False,
    db: Session = Depends(get_db),
):
    """Bảng tam giác hóa EDI/CDI theo môn/kỳ/khối (lọc theo school_id của user).

    Không truyền `subject_id`/`score_category` -> quét TOÀN TRƯỜNG, không cần dò tay từng môn.
    `flagged_only=true` -> chỉ trả dòng có cờ bất thường, sắp theo môn rồi khối (màn cảnh báo mặc định).
    """
    return exam_validity.compute_validity(
        db, user.school_id, semester_id, subject_id, score_category, grade_id, flagged_only
    )


@router.get(
    "/exam-validity/overview",
    response_model=SchoolValidityOverview,
    dependencies=[Depends(require_roles(*_OVERVIEW_ROLES))],
)
def get_exam_validity_overview(semester_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Tổng hợp toàn trường: đếm cờ + danh sách đề đáng rà soát nhất (BGH)."""
    return exam_validity.school_overview(db, user.school_id, semester_id)


@router.get(
    "/content-adjusted-ranking",
    response_model=list[ContentAdjustedRankRow],
    dependencies=[Depends(require_roles(*_OVERVIEW_ROLES))],
)
def get_content_adjusted_ranking(
    grade_id: UUID,
    semester_id: UUID,
    subject_id: UUID,
    user: CurrentUser,
    score_category: ScoreCategory = ScoreCategory.FINAL,
    db: Session = Depends(get_db),
):
    """Xếp hạng các lớp trong khối theo thực lực neo-nội-dung (độc lập TB cohort)."""
    return exam_validity.content_adjusted_ranking(db, user.school_id, grade_id, semester_id, subject_id, score_category)


@router.get(
    "/student-fairness",
    response_model=list[StudentFairnessRow],
    dependencies=[Depends(require_roles(*_FAIRNESS_ROLES))],
)
def get_student_fairness(
    semester_id: UUID,
    user: CurrentUser,
    subject_id: UUID | None = None,
    class_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    """Cảnh báo công bằng đánh giá: HS có TX vs GK/CK lệch bất thường so với CDI (chỉ ADMIN/PRINCIPAL).

    Không truyền `subject_id` -> quét TOÀN TRƯỜNG (mọi môn), không cần dò tay từng môn/khối.
    Mỗi cảnh báo kèm `evidence` — bằng chứng số liệu cụ thể. Đây là tín hiệu rà soát, KHÔNG phải
    kết luận tiêu cực đã xác nhận.
    """
    return student_fairness.compute_fairness_signals(db, user.school_id, semester_id, subject_id, class_id)
