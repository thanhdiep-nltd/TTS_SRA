"""Fix `teacher_assignments.class_id` mồ côi (101/102) trỏ về id thật của lớp 6A1/6A2.

Root cause (đã chẩn đoán):
- `seed_teacher_assignments` trước đây lookup lớp theo `code IN ('6A1','6A2')`,
  trong khi cột `code` thật là `CLASS_<school>_6A1`/`CLASS_<school>_6A2`
  (cột `fullname` mới chứa '6A1'/'6A2').
- `seed_teacher_assignments` còn chạy TRƯỚC `phase_dimensions` nên
  `dim_homeroom_class` còn rỗng → lookup thất bại → rơi vào fallback cứng
  101/102 → các dòng `teacher_assignments` trỏ id không tồn tại.

Script này tự tra id thật theo (fullname, so_school_id) rồi UPDATE các dòng
đang trỏ 101/102. An toàn: dừng (không sửa gì) nếu không tìm thấy id thật.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Bootstrap: cho phép import package `src` ở root workspace khi chạy từ scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from src.db.session import SessionLocal  # noqa: E402

SCHOOL_ID = 1
# class_id mồ côi (được ghi bởi fallback seed cũ) → fullname lớp thật tương ứng
ORPHAN_TO_NAME = {101: "6A1", 102: "6A2"}


def main() -> None:
    with SessionLocal() as s:
        print("=== Lớp thật 6A1/6A2 trong s360.dim_homeroom_class ===")
        class_rows = s.execute(
            text("""
                SELECT id, code, fullname, grade_id, so_school_id
                FROM s360.dim_homeroom_class
                WHERE fullname IN ('6A1', '6A2')
                ORDER BY fullname
            """)
        ).fetchall()
        for r in class_rows:
            print("  ", r)

        name_to_id = {r[2]: r[0] for r in class_rows if r[4] == SCHOOL_ID}
        mapping = {old: name_to_id.get(nm) for old, nm in ORPHAN_TO_NAME.items()}
        missing = [nm for old, nm in ORPHAN_TO_NAME.items() if mapping.get(old) is None]
        if missing:
            print(f"❌ Không tìm thấy id thật cho: {missing} (so_school_id={SCHOOL_ID}). Dừng, không sửa gì.")
            return

        print("\n=== Các dòng teacher_assignments đang trỏ class_id 101/102 ===")
        rows = s.execute(
            text("""
                SELECT ta.id, u.email, ta.role_context, ta.class_id, ta.grade_id, ta.subject_id
                FROM public.teacher_assignments ta
                JOIN public.users u ON u.id = ta.user_id
                WHERE ta.class_id IN (101, 102)
                ORDER BY ta.id
            """)
        ).fetchall()
        for r in rows:
            print("  ", r)
        print(f"  Tổng: {len(rows)} dòng sẽ được cập nhật.")

        print("\n=== UPDATE ===")
        for old_id, new_id in mapping.items():
            res = s.execute(
                text("UPDATE public.teacher_assignments SET class_id = :new WHERE class_id = :old"),
                {"old": old_id, "new": new_id},
            )
            print(f"  class_id {old_id} -> {new_id}: {res.rowcount} dòng")
        s.commit()

        print("\n=== Sau khi sửa: toàn bộ teacher_assignments ===")
        for r in s.execute(
            text("""
                SELECT ta.id, u.email, ta.role_context, ta.class_id, ta.grade_id, ta.subject_id, ta.is_active
                FROM public.teacher_assignments ta
                JOIN public.users u ON u.id = ta.user_id
                ORDER BY ta.id
            """)
        ).fetchall():
            print("  ", r)
        print("✅ Đã commit thành công.")


if __name__ == "__main__":
    main()
