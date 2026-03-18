from typing import Optional
import uuid
from sqlalchemy import ForeignKey, String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    os_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="stopped")
    cpu_cores: Mapped[int] = mapped_column(Integer, default=1)
    ram_mb: Mapped[int] = mapped_column(Integer, default=1024)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    lab_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("labs.id"), nullable=True)
    lab: Mapped[Optional["Lab"]] = relationship("Lab", back_populates="machines") # type: ignore