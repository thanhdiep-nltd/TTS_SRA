import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[ERROR] DATABASE_URL is not set in .env")
    sys.exit(1)

print(f"[INFO] Connecting to Database: {db_url[:40]}...")

import psycopg

sql_file = Path(__file__).resolve().parent.parent / "docs_vsf" / "schemas" / "merged" / "merged_vsf_sra_schema.sql"

if not sql_file.exists():
    print(f"[ERROR] SQL file not found at {sql_file}")
    sys.exit(1)

print(f"[INFO] Reading SQL DDL from: {sql_file}")
with open(sql_file, "r", encoding="utf-8") as f:
    sql_ddl = f.read()

try:
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            print("[INFO] Resetting Schemas (public, s360, t360, default)...")
            cur.execute("""
                DROP SCHEMA IF EXISTS s360 CASCADE;
                DROP SCHEMA IF EXISTS t360 CASCADE;
                DROP SCHEMA IF EXISTS "default" CASCADE;
                DROP SCHEMA IF EXISTS public CASCADE;
                CREATE SCHEMA public;
                CREATE SCHEMA s360;
                CREATE SCHEMA t360;
                CREATE SCHEMA "default";
            """)
            print("[INFO] Executing 55-table merged DDL schema on Neon PostgreSQL...")
            cur.execute(sql_ddl)
            print("[SUCCESS] 55-table Schema, Enums, Triggers, and Comments created successfully!")
except Exception as e:
    print(f"[ERROR] FAILED to execute DDL: {e}")
    sys.exit(1)
