from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings


def get_sqlalchemy_url() -> str:
    """Chuẩn hóa DATABASE_URL sang driver psycopg3 cho SQLAlchemy."""
    url = get_settings().database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


db_url = get_sqlalchemy_url()
if "postgresql" in db_url:
    # Pooler Neon (transaction-mode) chấp nhận kết nối bền; NullPool trước đây khiến mỗi
    # request mở lại TCP/TLS mới (100-300ms) kể cả /health. pool_recycle ngắn để tránh
    # kết nối bị pooler phía Neon âm thầm đóng khi idle lâu.
    engine = create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"options": "-c statement_timeout=3000ms"},
    )
else:
    engine = create_engine(db_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: mở một session cho mỗi request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
