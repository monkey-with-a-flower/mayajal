from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session,DeclarativeBase
from api.config import  DB_DIR, DB_PATH



class Base(DeclarativeBase):
    pass




DATABASE_URL = f"sqlite:///{DB_PATH}"

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