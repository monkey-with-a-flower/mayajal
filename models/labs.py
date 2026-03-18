import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Local imports
from api.db import Base


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="inactive")
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    owner: Mapped["User"] = relationship("User", back_populates="labs") # type: ignore
    machines: Mapped[list["Machine"]] = relationship("Machine", back_populates="lab") # type: ignore
