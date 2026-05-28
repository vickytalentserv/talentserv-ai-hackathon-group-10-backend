from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def _engine_kwargs() -> dict:
    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        return {"poolclass": NullPool, "pool_pre_ping": True}
    return {"pool_pre_ping": True, "pool_recycle": 3600}


engine = create_engine(settings.database_url, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
