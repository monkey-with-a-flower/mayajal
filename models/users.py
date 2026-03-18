import uuid
from sqlalchemy import String
from sqlalchemy.orm import  Mapped, mapped_column, relationship

# //local Imports
from api.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        nullable=False)
    name: Mapped[str] = mapped_column(String(100),unique=False,nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    labs: Mapped[list["Lab"]] = relationship("Lab", back_populates="owner") # type: ignore

