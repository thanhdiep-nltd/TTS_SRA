"""Seed demo TEVI (v_exam_validity) cho cấp 2 (THCS, khối 6-9).

scripts/seed_exam_validity_demo.py chỉ có 3 case ở cấp 3 (Khối 11), và mock_cdi_secondary.py đã
neo CDI quanh EDI cho TOÀN BỘ combo THCS (kể cả những combo điểm cao/thấp nhất) -> không còn combo
THCS nào "chưa map" để tạo case mới kiểu seed_exam_validity_demo.py. Script này thay vào đó NÂNG/HẠ
CDI của đúng vài đề `[MOCK]` đã có sẵn (ứng với combo điểm thật cao/thấp nhất ở THCS) để tạo case
thuyết phục, KHÔNG tạo đề/mapping mới, KHÔNG đụng tới đề có title khác '[MOCK]'.

QUAN TRỌNG: phải chọn combo nằm ở học kỳ ĐANG HIỆN HÀNH (`semesters.is_current=true`), vì dashboard
mặc định chỉ quét niên khóa/học kỳ hiện tại (xem CLAUDE.md §6) — case ở học kỳ cũ vẫn đúng trong DB
nhưng KHÔNG hiện ra cho người dùng thấy. Lần đầu chọn nhầm 3/4 case rơi vào học kỳ cũ -> đã revert
về CDI gốc, chọn lại đúng học kỳ hiện tại (`ab4320d4-...`, niên khóa đang dùng để demo).

- INFLATION_OR_LEAK #1: Giáo dục công dân, Khối 7, Cuối kỳ — mean thật 6.93 (EDI=0.307), nâng CDI
  lên 0.65 (đề khó) -> divergence ~ -0.34.
- INFLATION_OR_LEAK #2: Tin học, Khối 6, Giữa kỳ — mean thật 6.62 (EDI=0.338), nâng CDI lên 0.65
  -> divergence ~ -0.31.
- LEARNING_GAP: Ngữ văn, Khối 8, Cuối kỳ — mean thật 4.50 (EDI=0.550), hạ CDI xuống 0.25 (đề dễ)
  -> divergence ~ +0.30: đề không khó mà học sinh vẫn làm kém.

Idempotent: luôn SET về đúng giá trị cố định.
Chạy: python scripts/seed_tevi_secondary_demo.py
"""

from sqlalchemy import text

from src.db.session import SessionLocal

# Revert 3 case chọn nhầm học kỳ cũ (không hiện trên dashboard) về đúng CDI gốc trước khi sửa.
_REVERT_OLD_SEMESTER_MISTAKE = {
    "e153622c-edcd-4866-b74e-62e671cc85e3": 0.293,  # KHTN Khối 9 CK (HK1 cũ) -> về lại VALID
    "ffde1cf0-a8d8-410d-9111-c8affb016474": 0.348,  # Lịch sử-Địa lý Khối 9 CK (HK1 cũ) -> về lại VALID
    "88880285-d6bd-4709-90cb-28a320904e48": 0.477,  # Ngữ văn Khối 8 CK (HK1 cũ) -> về lại VALID
}

# Case demo đúng, nằm trong học kỳ hiện tại (ab4320d4 - HK2 niên khóa đang dùng để demo).
_CDI_OVERRIDES = {
    "f178b528-df1b-45f8-9277-23ac272e8436": 0.65,  # GDCD Khối 7 CK (mean thật 6.93) -> INFLATION_OR_LEAK
    "7d0f1239-b23c-4a0f-9633-3fddca90c2b8": 0.65,  # Tin học Khối 6 GK (mean thật 6.62) -> INFLATION_OR_LEAK
    "9f3cdc5f-209b-4ad8-a927-a48b17f2d255": 0.25,  # Ngữ văn Khối 8 CK (mean thật 4.50) -> LEARNING_GAP
}


def _apply(db, overrides: dict[str, float]) -> int:
    n = 0
    for paper_id, cdi in overrides.items():
        result = db.execute(
            text("UPDATE exam_papers SET content_difficulty = :c WHERE id = :i AND title LIKE '[MOCK]%'"),
            {"c": cdi, "i": paper_id},
        )
        n += result.rowcount
    return n


def main() -> None:
    db = SessionLocal()
    try:
        n_revert = _apply(db, _REVERT_OLD_SEMESTER_MISTAKE)
        n_new = _apply(db, _CDI_OVERRIDES)
        db.commit()
        print(f"Done. Da revert {n_revert} de hoc ky cu, ap dung {n_new} de demo o hoc ky hien tai.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
