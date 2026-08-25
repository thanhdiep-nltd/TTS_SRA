"""Script seed index RAG cho các cuốn sách SGK đã nạp sẵn trong hệ thống.

1. Quét các file PDF trong uploads/curriculum_books/{book_id}.pdf.
2. Với sách chưa có start_page/end_page trong curriculum_units:
   - Gọi extract_book_structure() để trích xuất dải trang từ Mục Lục (TOC).
   - Cập nhật start_page, end_page cho các node trong curriculum_units.
3. Gọi index_book_chunks() để cắt đề mục theo Heading và nhúng vector vào PostgreSQL pgvector.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Đảm bảo import được src
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select, update
from src.api.v1.curriculum import _BOOK_DIR, _book_pdf_path
from src.db.session import SessionLocal
from src.models.tables import CurriculumBook, CurriculumUnit
from src.observability import logger
from src.services.curriculum_chunking import index_book_chunks
from src.services.curriculum_ingest import extract_book_structure


def seed_existing_books():
    print("=" * 60)
    print("BẮT ĐẦU SEED VÀ INDEX CHUNKS CHO CÁC SÁCH SGK ĐÃ CÓ TRONG HỆ THỐNG")
    print("=" * 60)

    db = SessionLocal()
    try:
        books = list(db.execute(select(CurriculumBook).order_by(CurriculumBook.id)).scalars().all())
        if not books:
            print("Không tìm thấy cuốn sách nào trong CSDL.")
            return

        print(f"Tìm thấy {len(books)} cuốn sách trong CSDL.")

        for book in books:
            pdf_path = _book_pdf_path(book.id)
            print(f"\n--- Đang xử lý Cuốn ID {book.id}: {book.title} (Môn {book.subject_code}, Khối {book.grade_number}) ---")

            if not pdf_path.exists():
                print(f"⚠️ Không tìm thấy file PDF tại: {pdf_path}. Bỏ qua.")
                continue

            # Kiểm tra xem các units của sách đã có start_page chưa
            units = list(
                db.execute(
                    select(CurriculumUnit)
                    .where(CurriculumUnit.book_id == book.id)
                    .order_by(CurriculumUnit.grade_number, CurriculumUnit.code)
                ).scalars().all()
            )
            print(f"Sách có {len(units)} units trong CSDL.")

            missing_pages = any(u.start_page is None for u in units)

            if missing_pages and units:
                print("Dò dải trang [start_page, end_page] từ Mục Lục SGK...")
                try:
                    pdf_bytes = pdf_path.read_bytes()
                    chapters, page_map, warnings, tmp_path = extract_book_structure(pdf_bytes)
                    tmp_path.unlink(missing_ok=True)

                    # Ánh xạ dải trang vào units
                    code_to_unit = {u.code: u for u in units}
                    name_to_unit = {u.name.strip().lower(): u for u in units}

                    updated_count = 0
                    base = book.subject_code.upper().strip()
                    if base.endswith(f"_{book.grade_number}"):
                        base = base[: -len(f"_{book.grade_number}")]
                    prefix = f"{base}{book.grade_number}"
                    for c_idx, ch in enumerate(chapters, start=1):
                        c_code = f"{prefix}_C{c_idx}"
                        ch_unit = code_to_unit.get(c_code) or name_to_unit.get(ch["name"].strip().lower())
                        if ch_unit and ch.get("start_page") is not None:
                            ch_unit.start_page = ch["start_page"]
                            ch_unit.end_page = ch["end_page"]
                            updated_count += 1

                        for l_idx, lesson in enumerate(ch.get("lessons", []), start=1):
                            l_code = f"{c_code}_B{l_idx}"
                            l_unit = code_to_unit.get(l_code) or name_to_unit.get(lesson["name"].strip().lower())
                            if l_unit and lesson.get("start_page") is not None:
                                l_unit.start_page = lesson["start_page"]
                                l_unit.end_page = lesson["end_page"]
                                updated_count += 1

                    db.commit()
                    print(f"✅ Đã cập nhật start_page/end_page cho {updated_count} units.")
                except Exception as exc:
                    print(f"❌ Lỗi khi dò Mục Lục: {exc}")
                    # Nếu lỗi dò mục lục, fallback gán dải trang đều theo số trang PDF
                    import fitz
                    with fitz.open(pdf_path) as doc:
                        total_p = doc.page_count
                    pages_per_unit = max(1, total_p // max(1, len(units)))
                    for idx, u in enumerate(units):
                        u.start_page = idx * pages_per_unit
                        u.end_page = min(total_p - 1, (idx + 1) * pages_per_unit - 1)
                    db.commit()
                    print(f"⚠️ Đã fallback gán dải trang tuyến tính cho {len(units)} units.")

            # Tiến hành Chunking và nhúng Vector vào pgvector
            print("Đang thực hiện Chunking theo Đề mục & Embedding vào pgvector...")
            chunk_count = index_book_chunks(db, book.id, pdf_path)
            print(f"🎉 Hoàn tất: Đã index thành công {chunk_count} chunks vào PostgreSQL!")
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("HOÀN TẤT TOÀN BỘ TIẾN TRÌNH SEED VÀ INDEX!")
    print("=" * 60)


if __name__ == "__main__":
    seed_existing_books()
