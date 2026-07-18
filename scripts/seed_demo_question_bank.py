"""Seed ngân hàng câu hỏi DEMO cho 2 môn Toán + KHTN (THCS, khối 6-9).

Idempotent: tạo curriculum_units nếu chưa có (get_or_create theo subject+grade+code), rồi gọi
item_generation.generate_items() THẬT (LLM + RAG) để sinh câu DRAFT cho mỗi chủ đề. Cần:
  - Embedding sidecar chạy ở EMBEDDING_SERVICE_URL (docker compose up -d embedding-service)
  - Qdrant đã có nội dung SGK Toán/KHTN khối 6-9 (đã nạp trước)
  - OPENAI_API_KEY hợp lệ trong .env (mỗi câu tốn ~2 lệnh gọi LLM: sinh + tự giải lại)

Chạy: python scripts/seed_demo_question_bank.py
"""

import sys

from sqlalchemy import select

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import CurriculumUnit, Subject, User
from src.services import item_generation, retrieval

# (subject_code, grade_number, code, name) — chủ đề tiêu biểu GDPT 2018, không cần phủ hết SGK cho demo.
_UNITS: list[tuple[str, int, str, str]] = [
    # Toán học
    ("TOAN", 6, "TOAN6-TAPHOP", "Tập hợp các số tự nhiên"),
    ("TOAN", 6, "TOAN6-SONGUYEN", "Số nguyên"),
    ("TOAN", 6, "TOAN6-HINHPHANG", "Hình học trực quan: hình phẳng cơ bản"),
    ("TOAN", 7, "TOAN7-SOHUUTI", "Số hữu tỉ"),
    ("TOAN", 7, "TOAN7-BIEUTHUC", "Biểu thức đại số"),
    ("TOAN", 7, "TOAN7-TAMGIAC", "Tam giác"),
    ("TOAN", 8, "TOAN8-PHANTHUC", "Phân thức đại số"),
    ("TOAN", 8, "TOAN8-HAMSO", "Hàm số và đồ thị"),
    ("TOAN", 8, "TOAN8-DONGDANG", "Tam giác đồng dạng"),
    ("TOAN", 9, "TOAN9-PHUONGTRINH", "Phương trình và hệ phương trình"),
    ("TOAN", 9, "TOAN9-HAMSOBAC2", "Hàm số bậc nhất, bậc hai"),
    ("TOAN", 9, "TOAN9-DUONGTRON", "Đường tròn"),
    # Khoa học tự nhiên
    ("KHTN", 6, "KHTN6-MODAU", "Mở đầu về Khoa học tự nhiên và các phép đo"),
    ("KHTN", 6, "KHTN6-TEBAO", "Tế bào - đơn vị cơ sở của sự sống"),
    ("KHTN", 6, "KHTN6-CHAT", "Chất và sự biến đổi của chất"),
    ("KHTN", 7, "KHTN7-NGUYENTU", "Nguyên tử, nguyên tố hóa học, bảng tuần hoàn"),
    ("KHTN", 7, "KHTN7-TRAODOICHAT", "Trao đổi chất và chuyển hóa năng lượng ở sinh vật"),
    ("KHTN", 7, "KHTN7-ANHSANG", "Ánh sáng"),
    ("KHTN", 8, "KHTN8-PHANUNG", "Phản ứng hóa học"),
    ("KHTN", 8, "KHTN8-DIEN", "Điện"),
    ("KHTN", 8, "KHTN8-HEVANDONG", "Hệ vận động ở người"),
    ("KHTN", 9, "KHTN9-NANGLUONG", "Năng lượng và sự biến đổi"),
    ("KHTN", 9, "KHTN9-DITRUYEN", "Di truyền và biến dị"),
    ("KHTN", 9, "KHTN9-HESINHTHAI", "Hệ sinh thái"),
]

_BLOOM_LEVEL = 2  # Hiểu — phù hợp demo trắc nghiệm phổ thông
_QUESTION_TYPE = enums.QuestionType.MCQ
_COUNT_PER_UNIT = 5


def _get_or_create_unit(db, subject_id, grade_number: int, code: str, name: str) -> CurriculumUnit:
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
        print(f"    + tạo curriculum_unit {code}")
    return unit


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.execute(select(User).where(User.role == enums.UserRole.ADMIN)).scalars().first()
        if admin is None:
            print("Không tìm thấy user ADMIN — chạy scripts/create_admin.py trước.")
            sys.exit(1)

        subjects = {
            row.code: row
            for row in db.execute(
                select(Subject).where(Subject.code.in_(["TOAN", "KHTN"]), Subject.school_id == admin.school_id)
            ).scalars().all()
        }
        missing = {"TOAN", "KHTN"} - subjects.keys()
        if missing:
            print(f"Thiếu môn {missing} ở trường {admin.school_id} — kiểm tra lại seed subjects.")
            sys.exit(1)

        total_created, total_failed = 0, 0
        for subject_code, grade_number, code, name in _UNITS:
            subject = subjects[subject_code]
            unit = _get_or_create_unit(db, subject.id, grade_number, code, name)
            db.commit()

            print(f"[{subject_code} - lớp {grade_number}] {name} ({code})...", end=" ")
            try:
                created = item_generation.generate_items(
                    db, admin.school_id, admin.id, subject.id, grade_number, unit.id,
                    _BLOOM_LEVEL, _QUESTION_TYPE, _COUNT_PER_UNIT,
                )
                print(f"+{len(created)} câu")
                total_created += len(created)
            except item_generation.InsufficientContextError as exc:
                print(f"BỎ QUA (không có ngữ cảnh SGK): {exc}")
                total_failed += 1
            except retrieval.RetrievalUnavailableError as exc:
                print(f"LỖI RAG, dừng seed: {exc}")
                sys.exit(1)

        print(f"\nHoàn tất: {total_created} câu DRAFT đã tạo, {total_failed} chủ đề bị bỏ qua.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
