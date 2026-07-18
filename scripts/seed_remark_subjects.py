"""Seed các môn đánh giá bằng nhận xét (Đạt/Chưa đạt) cho THCS & THPT.

Idempotent: upsert theo (school_id, code); đặt applicable_level theo cấp + assessment_type=REMARK.
Chạy: python scripts/seed_remark_subjects.py
"""

from sqlalchemy import select

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import Grade, Subject

# code -> tên môn, theo cấp học
SECONDARY_SUBJECTS = [
    ("GDTC", "Giáo dục thể chất"),
    ("AN", "Âm nhạc"),
    ("MT", "Mĩ thuật"),
]
HIGH_SUBJECTS = [
    ("GDTC", "Giáo dục thể chất"),
    ("GDQP", "Giáo dục quốc phòng và an ninh"),
    ("HDTN", "Hoạt động trải nghiệm, hướng nghiệp"),
    ("GDDP", "Nội dung giáo dục địa phương"),
]


def _school_id_for_level(db, level: enums.SchoolLevel):
    row = db.execute(select(Grade.school_id).where(Grade.school_level == level).limit(1)).first()
    return row[0] if row else None


def _upsert(db, school_id, level, code, name) -> str:
    subj = db.execute(
        select(Subject).where(Subject.school_id == school_id, Subject.code == code)
    ).scalars().first()
    if subj is None:
        db.add(Subject(school_id=school_id, code=code, name=name, applicable_level=level,
                       assessment_type=enums.AssessmentType.REMARK, is_active=True))
        return f"  + {code} ({name})"
    subj.assessment_type = enums.AssessmentType.REMARK
    subj.is_active = True
    return f"  = {code} (đã có, set REMARK)"


def main() -> None:
    db = SessionLocal()
    try:
        for level, subjects in (
            (enums.SchoolLevel.SECONDARY, SECONDARY_SUBJECTS),
            (enums.SchoolLevel.HIGH, HIGH_SUBJECTS),
        ):
            school_id = _school_id_for_level(db, level)
            if school_id is None:
                print(f"{level}: không tìm thấy trường — bỏ qua")
                continue
            print(f"{level} (school={school_id}):")
            for code, name in subjects:
                print(_upsert(db, school_id, level, code, name))
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
