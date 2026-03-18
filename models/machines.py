from typing import Optional
import uuid
from sqlalchemy import ForeignKey, String, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    imageUrl: Mapped[str] = mapped_column(String,nullable=False)
    volumes:Mapped[Optional[dict | None]] = mapped_column(JSON,nullable=True)
    env: Mapped[Optional[dict | None]] = mapped_column(JSON,nullable=True)
    restart_policy: Mapped[Optional[str]] = mapped_column(String(36),default="Unless stopped",nullable=False)
    commands: Mapped[Optional[str]] = mapped_column(JSON,nullable=True)
    console: Mapped[Optional[bool]] =mapped_column(Boolean,default=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    os_type: Mapped[str] = mapped_column(String(50), nullable=False)
    lab_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("labs.id"), nullable=True)
    lab: Mapped[Optional["Lab"]] = relationship("Lab", back_populates="machines") # type: ignore