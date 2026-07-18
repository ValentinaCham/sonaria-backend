from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _make_engine():
    url = settings.DATABASE_URL
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


class Base(DeclarativeBase):
    pass


def get_connection():
    if engine is None:
        raise RuntimeError("DATABASE_URL no está configurada")
    return engine.connect()
