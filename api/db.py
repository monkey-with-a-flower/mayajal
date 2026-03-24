from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session,DeclarativeBase
from pathlib import Path

from api.config import  DB_DIR



class Base(DeclarativeBase):
    pass




DATABASE_URL = f"sqlite:///{DB_DIR}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()