from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

_db_url = settings.database_url.replace("postgres://", "postgresql://", 1)
engine = create_engine(
    _db_url,
    connect_args={"check_same_thread": False} if "sqlite" in _db_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
