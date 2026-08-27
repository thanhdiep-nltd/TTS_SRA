from src.db.session import SessionLocal
from src.models.tables import CurriculumBook, CurriculumUnit
from sqlalchemy import select

db = SessionLocal()
try:
    for book_id in [71, 72]:
        book = db.get(CurriculumBook, book_id)
        if not book:
            continue
        print(f"=== BOOK {book_id}: {book.title} ({book.subject_code}, Grade {book.grade_number}) ===")
        units = list(db.execute(select(CurriculumUnit).where(CurriculumUnit.book_id == book_id).order_by(CurriculumUnit.id)).scalars().all())
        for u in units[:10]:
            print(f"  Unit id={u.id}, code={u.code}, parent_id={u.parent_id}, start_page={u.start_page}, end_page={u.end_page}, name={u.name}")
        print(f"  Total units: {len(units)}")
finally:
    db.close()
