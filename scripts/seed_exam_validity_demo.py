"""Seed demo cho TEVI (tam giác hóa độ khó đề thi): tạo exam_papers + exam_column_mappings +
curriculum_units + exam_competencies cho 2 đề thật (lấy từ mv_exam_difficulty đang có điểm),
để v_exam_validity ra cờ thật (LEARNING_GAP / INFLATION_OR_LEAK) thay vì toàn NO_CONTENT.

Idempotent theo (subject_id, semester_id, score_category, grade_id) — chạy lại không tạo trùng.
Chạy: python scripts/seed_exam_validity_demo.py
"""

from datetime import UTC, datetime

from sqlalchemy import select, text

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import CurriculumUnit, ExamColumnMapping, ExamCompetency, ExamPaper
from src.services.content_difficulty import cdi_from_bloom_mix as _cdi_bloom

# Mỗi case: chọn 1 dòng (subject, semester, score_category, grade) đã có điểm thật trong
# mv_exam_difficulty, gán nội dung đề theo đúng ví dụ §13 design doc (70% Bloom 1-2, 30% Bloom 3
# -> CDI_bloom ~ 0.325, đề dễ-trung bình) để divergence bộc lộ rõ so với điểm thực tế.
CASES = [
    {
        "label": "LEARNING_GAP demo (mean thấp trên đề dễ-trung bình)",
        "subject_id": "3e8993c6-53d2-48a7-a526-bc969a8c2515",  # Giáo dục kinh tế và pháp luật
        "semester_id": "f2a08ba8-f72e-4798-b95a-3c0de81d35e4",
        "grade_id": "aa93e9e4-0678-41ac-a82f-c05484788660",  # Khối 10
        "score_category": enums.ScoreCategory.FINAL,
        "title": "Đề thi cuối kỳ - Giáo dục kinh tế và pháp luật - Khối 10 - HK1 (demo TEVI)",
        # 70% Bloom 1-2, 30% Bloom 3 -> đề dễ-trung bình, nhưng mean thực tế (3.98) vẫn thấp -> LEARNING_GAP.
        "bloom_mix": [(1, 0.40), (2, 0.30), (3, 0.30)],
    },
    {
        "label": "INFLATION_OR_LEAK demo (mean rất cao trên đề khó)",
        "subject_id": "bf351fac-3e53-40e9-89fc-fc02d380dfbd",  # Sinh học
        "semester_id": "8d3e09b4-bf14-4ed5-ac73-290d9f02c10c",
        "grade_id": "c71efa5e-77b3-40ef-a82f-3441f78a2fa1",  # Khối 11
        "score_category": enums.ScoreCategory.FINAL,
        "title": "Đề thi cuối kỳ - Sinh học - Khối 11 - HK1 (demo TEVI)",
        # Thiên về Vận dụng/Phân tích/Sáng tạo (Bloom 3-5) -> đề khó, nhưng mean thực tế (8.73) lại
        # rất cao -> phân kỳ mạnh, nghi lạm phát điểm/lộ đề.
        "bloom_mix": [(3, 0.40), (4, 0.30), (5, 0.30)],
    },
    {
        "label": "INFLATION_OR_LEAK demo #2 (Hóa học, mean cao 7.70 trên đề rất khó)",
        "subject_id": "16a3b6db-cf9a-4b09-afd9-0264c91aa624",  # Hóa học
        "semester_id": "f2a08ba8-f72e-4798-b95a-3c0de81d35e4",
        "grade_id": "c71efa5e-77b3-40ef-a82f-3441f78a2fa1",  # Khối 11
        "score_category": enums.ScoreCategory.FINAL,
        "title": "Đề thi cuối kỳ - Hóa học - Khối 11 - HK1 (demo TEVI)",
        # Thiên hẳn về Phân tích/Đánh giá/Sáng tạo (Bloom 4-6) -> CDI ~0.83, mean thực tế chỉ 7.70
        # (EDI ~0.23) -> divergence ~ -0.6, phân kỳ rất mạnh, case thuyết phục cho demo BGK.
        "bloom_mix": [(4, 0.30), (5, 0.40), (6, 0.30)],
    },
    {
        "label": "INFLATION_OR_LEAK demo #3 (Lịch sử, mean cao 7.83 trên đề rất khó)",
        "subject_id": "b51e94de-4906-423e-ba6a-27859b6ed486",  # Lịch sử
        "semester_id": "06140937-cee4-4c02-814b-ebe3a0ef1c1c",
        "grade_id": "c71efa5e-77b3-40ef-a82f-3441f78a2fa1",  # Khối 11
        "score_category": enums.ScoreCategory.FINAL,
        "title": "Đề thi cuối kỳ - Lịch sử - Khối 11 - HK1 (demo TEVI)",
        "bloom_mix": [(4, 0.30), (5, 0.40), (6, 0.30)],
    },
]


def _resolve_uploader(db, school_id) -> str | None:
    row = db.execute(
        text(
            "SELECT id FROM users WHERE school_id = :sid AND role IN ('ADMIN', 'PRINCIPAL') LIMIT 1"
        ),
        {"sid": school_id},
    ).first()
    return row[0] if row else None


def _get_or_create_unit(db, subject_id, grade_number, code, name) -> CurriculumUnit:
    unit = db.execute(
        select(CurriculumUnit).where(
            CurriculumUnit.subject_id == subject_id,
            CurriculumUnit.grade_number == grade_number,
            CurriculumUnit.code == code,
        )
    ).scalar_one_or_none()
    if unit is None:
        unit = CurriculumUnit(subject_id=subject_id, grade_number=grade_number, code=code, name=name)
        db.add(unit)
        db.flush()
    return unit


def _seed_case(db, case: dict) -> str:
    existing = db.execute(
        select(ExamColumnMapping).where(
            ExamColumnMapping.subject_id == case["subject_id"],
            ExamColumnMapping.semester_id == case["semester_id"],
            ExamColumnMapping.score_category == case["score_category"],
            ExamColumnMapping.grade_id == case["grade_id"],
        )
    ).scalar_one_or_none()
    if existing is not None:
        return f"  = {case['label']}: đã có mapping (exam_paper_id={existing.exam_paper_id}), bỏ qua"

    subject = db.execute(text("SELECT school_id FROM subjects WHERE id = :i"), {"i": case["subject_id"]}).first()
    grade = db.execute(text("SELECT grade_number FROM grades WHERE id = :i"), {"i": case["grade_id"]}).first()
    if subject is None or grade is None:
        return f"  ! {case['label']}: không tìm thấy subject/grade, bỏ qua"

    school_id = subject[0]
    grade_number = grade[0]
    uploader_id = _resolve_uploader(db, school_id)
    if uploader_id is None:
        return f"  ! {case['label']}: không tìm thấy ADMIN/PRINCIPAL của trường {school_id}, bỏ qua"

    bloom_mix = case["bloom_mix"]
    cdi = _cdi_bloom(bloom_mix)

    paper = ExamPaper(
        school_id=school_id,
        subject_id=case["subject_id"],
        semester_id=case["semester_id"],
        grade_id=case["grade_id"],
        title=case["title"],
        difficulty=enums.Difficulty.MEDIUM,
        uploaded_by=uploader_id,
        content_difficulty=cdi,
        content_analyzed_at=datetime.now(UTC),
        content_source=enums.FileType.OTHER,
    )
    db.add(paper)
    db.flush()

    mapping = ExamColumnMapping(
        subject_id=case["subject_id"],
        semester_id=case["semester_id"],
        score_category=case["score_category"],
        column_index=1,
        grade_id=case["grade_id"],
        exam_paper_id=paper.id,
        mapped_by=uploader_id,
    )
    db.add(mapping)

    units = [
        _get_or_create_unit(db, case["subject_id"], grade_number, f"DEMO-B{bloom}", f"Chủ đề demo Bloom {bloom}")
        for bloom, _ in bloom_mix
    ]
    for (bloom, weight), unit in zip(bloom_mix, units):
        db.add(ExamCompetency(exam_paper_id=paper.id, unit_id=unit.id, weight=weight, bloom_level=bloom))

    return f"  + {case['label']}: tạo exam_paper={paper.id}, CDI={cdi}"


def main() -> None:
    db = SessionLocal()
    try:
        for case in CASES:
            print(_seed_case(db, case))
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
