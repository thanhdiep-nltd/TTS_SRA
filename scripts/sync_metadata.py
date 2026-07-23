"""Script đồng bộ tất cả danh mục của trường học vào kho s360.metadata_index dùng Hybrid Search."""
import sys
from sqlalchemy import text
from src.db.session import SessionLocal
from src.services.metadata_indexer import sync_school_metadata

def main():
    school_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"[INFO] Dang dong bo Metadata Index cho truong so_school_id = {school_id}...")
    
    count = sync_school_metadata(school_id)
    print(f"[SUCCESS] Da dong bo thanh cong {count} ban ghi danh muc vao s360.metadata_index!")

    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT entity_type, entity_name, exact_code, exact_id FROM s360.metadata_index WHERE so_school_id = :sid"),
            {"sid": school_id}
        ).fetchall()
        print("\n[LIST] Danh sach danh muc da nap vao Kho Metadata:")
        for r in rows:
            print(f"  - [{r[0]}] {r[1]} -> Code: '{r[2]}', ID: {r[3]}")

if __name__ == "__main__":
    main()
