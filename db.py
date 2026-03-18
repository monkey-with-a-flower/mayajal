from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session,DeclarativeBase
from pathlib import Path



class Base(DeclarativeBase):
    pass



BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'db' / 'mayajal.db'}"

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