"""Demo end-to-end: duyệt câu DRAFT (auto-approve) -> tạo ma trận đề -> ráp đề -> chốt đề.

Minh họa trọn vẹn luồng AI Exam Generation (xem docs/exam_generation_design.md):
  sinh câu (đã chạy ở scripts/seed_demo_question_bank.py) -> DUYỆT NGƯỜI -> ráp đề nhiều mã đề
  -> chốt đề (sinh exam_papers + exam_competencies, TEVI tính CDI ngay không cần OCR).

Auto-approve ở đây CHỈ cho mục đích demo: chỉ duyệt câu có self_consistency="match" (đã qua
guardrail). Câu "mismatch" CỐ TÌNH bị bỏ lại ở DRAFT để minh họa guardrail thật sự chặn được
câu khả nghi, không tự động duyệt mọi thứ.

Chạy: python scripts/demo_assemble_exam.py [--subject TOAN] [--grade 8]
"""

import argparse
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import (
    AcademicYear,
    CurriculumUnit,
    ExamBlueprint,
    ExamPaper,
    Grade,
    QuestionItem,
    Semester,
    Subject,
    User,
)
from src.schemas.exam_generation import AssembleRequest
from src.services import exam_assembly


def _auto_approve_matching_items(db, school_id, subject_id, grade_number: int, reviewer_id) -> tuple[int, int]:
    """Duyệt câu DRAFT có self_consistency=match; để lại câu mismatch cho người rà soát thật."""
    items = db.execute(
        select(QuestionItem).where(
            QuestionItem.school_id == school_id,
            QuestionItem.subject_id == subject_id,
            QuestionItem.grade_number == grade_number,
            QuestionItem.status == enums.ItemStatus.DRAFT,
        )
    ).scalars().all()

    approved, left_for_review = 0, 0
    for item in items:
        if item.provenance.get("self_consistency") == "match":
            item.status = enums.ItemStatus.APPROVED
            item.reviewed_by = reviewer_id
            item.reviewed_at = datetime.now(UTC)
            approved += 1
        else:
            left_for_review += 1
    db.commit()
    return approved, left_for_review


def _distribute(total: int, n_buckets: int) -> list[int]:
    """Chia `total` câu đều cho `n_buckets` ô, phần dư dồn vào các ô đầu."""
    base, remainder = divmod(total, n_buckets)
    return [base + 1 if i < remainder else base for i in range(n_buckets)]


def _build_blueprint_cells(db, school_id, subject_id, grade_number: int, total_questions: int) -> list[dict]:
    """Lấy các unit có câu APPROVED, chia đều số câu cần lấy cho mỗi unit (1 điểm/câu)."""
    units = db.execute(
        select(CurriculumUnit.id, CurriculumUnit.name)
        .join(QuestionItem, QuestionItem.unit_id == CurriculumUnit.id)
        .where(
            QuestionItem.school_id == school_id,
            QuestionItem.subject_id == subject_id,
            QuestionItem.grade_number == grade_number,
            QuestionItem.status == enums.ItemStatus.APPROVED,
        )
        .distinct()
    ).all()
    if not units:
        raise SystemExit(f"Không có unit nào có câu APPROVED cho môn/khối này (grade={grade_number}).")

    counts = _distribute(total_questions, len(units))
    cells = []
    for (unit_id, unit_name), n in zip(units, counts, strict=True):
        if n == 0:
            continue
        cells.append(
            {
                "unit_id": str(unit_id),
                "bloom_level": 2,
                "question_type": enums.QuestionType.MCQ.value,
                "num_questions": n,
                "points_each": 1.0,
            }
        )
        print(f"    ô ma trận: {unit_name} x{n} câu")
    return cells


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="TOAN", help="Mã môn (mặc định TOAN)")
    parser.add_argument("--grade", type=int, default=8, help="Khối lớp (mặc định 8)")
    parser.add_argument("--total-questions", type=int, default=10, help="Tổng số câu trong đề (mặc định 10)")
    parser.add_argument("--num-variants", type=int, default=2, help="Số mã đề (mặc định 2)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        admin = db.execute(select(User).where(User.role == enums.UserRole.ADMIN)).scalars().first()
        if admin is None:
            sys.exit("Không tìm thấy user ADMIN.")

        subject = db.execute(
            select(Subject).where(Subject.code == args.subject, Subject.school_id == admin.school_id)
        ).scalars().first()
        if subject is None:
            sys.exit(f"Không tìm thấy môn {args.subject} ở trường {admin.school_id}.")

        grade = db.execute(
            select(Grade).where(Grade.grade_number == args.grade, Grade.school_id == admin.school_id)
        ).scalars().first()
        if grade is None:
            sys.exit(f"Không tìm thấy khối {args.grade} ở trường {admin.school_id}.")

        semester = db.execute(
            select(Semester)
            .join(AcademicYear, AcademicYear.id == Semester.academic_year_id)
            .where(AcademicYear.school_id == admin.school_id, AcademicYear.is_current.is_(True), Semester.name == "HK1")
        ).scalars().first()
        if semester is None:
            sys.exit("Không tìm thấy học kỳ HK1 hiện hành.")

        print(f"=== Demo ráp đề {args.subject} khối {args.grade} ({semester.name}) ===\n")

        print("1) Duyệt câu (auto-approve câu self_consistency=match, để lại câu mismatch cho người rà soát)")
        approved, left = _auto_approve_matching_items(db, admin.school_id, subject.id, args.grade, admin.id)
        print(f"   -> đã duyệt {approved} câu, còn {left} câu DRAFT chờ rà soát thủ công\n")

        print("2) Tạo ma trận đề (exam_blueprints)")
        cells = _build_blueprint_cells(db, admin.school_id, subject.id, args.grade, args.total_questions)

        blueprint = ExamBlueprint(
            school_id=admin.school_id,
            subject_id=subject.id,
            grade_number=args.grade,
            score_category=enums.ScoreCategory.FINAL,
            title=f"[DEMO] Đề Cuối kỳ {args.subject} khối {args.grade} - {semester.name}",
            total_points=float(sum(c["num_questions"] * c["points_each"] for c in cells)),
            target_difficulty=0.45,
            cells=cells,
            created_by=admin.id,
        )
        db.add(blueprint)
        db.commit()
        db.refresh(blueprint)
        print(f"   -> blueprint_id={blueprint.id}, total_points={blueprint.total_points}\n")

        print(f"3) Ráp đề ({args.num_variants} mã đề)")
        req = AssembleRequest(
            blueprint_id=blueprint.id, semester_id=semester.id, grade_id=grade.id, num_variants=args.num_variants
        )
        gen = exam_assembly.assemble(db, admin, req)
        print(f"   -> generated_exam_id={gen.id}, status={gen.status}\n")

        print("4) Chốt đề (sinh exam_papers + exam_competencies — TEVI-ready)")
        gen = exam_assembly.finalize(db, admin, gen.id)
        paper = db.get(ExamPaper, gen.exam_paper_id)
        print(f"   -> exam_paper_id={paper.id}")
        print(f"   -> num_questions={paper.num_questions}, total_points={paper.total_points}")
        print(f"   -> content_difficulty (CDI)={paper.content_difficulty}, difficulty={paper.difficulty}")
        print(f"   -> topics={paper.topics}\n")

        print(f"=== Hoàn tất demo. Xem chi tiết mã đề qua GET /api/v1/exams/{gen.id} ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
