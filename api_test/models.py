import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Table, Column, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api_test.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class LabStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class SessionStatus(str, enum.Enum):
    running = "running"
    stopped = "stopped"


scenario_machines = Table(
    "scenario_machines",
    Base.metadata,
    Column("scenario_id", ForeignKey("scenarios.id", ondelete="CASCADE"), primary_key=True),
    Column("machine_id", ForeignKey("machines.id", ondelete="CASCADE"), primary_key=True),
)


lab_machines = Table(
    "lab_machines",
    Base.metadata,
    Column("lab_id", ForeignKey("labs.id", ondelete="CASCADE"), primary_key=True),
    Column("machine_id", ForeignKey("machines.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.student)
    entra_object_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    created_labs: Mapped[list["Lab"]] = relationship(back_populates="owner")
    assignments: Mapped[list["LabAssignment"]] = relationship(back_populates="student", cascade="all, delete-orphan", foreign_keys="LabAssignment.student_id")
    sessions: Mapped[list["LabSession"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    scenarios: Mapped[list["Scenario"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    image_url: Mapped[str] = mapped_column(String(500))
    os_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(500), default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    labs: Mapped[list["Lab"]] = relationship(secondary=lab_machines, back_populates="machines")


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[LabStatus] = mapped_column(Enum(LabStatus), default=LabStatus.draft)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner: Mapped[User] = relationship(back_populates="created_labs")
    machines: Mapped[list[Machine]] = relationship(secondary=lab_machines, back_populates="labs")
    assignments: Mapped[list["LabAssignment"]] = relationship(back_populates="lab", cascade="all, delete-orphan")
    sessions: Mapped[list["LabSession"]] = relationship(back_populates="lab", cascade="all, delete-orphan")


class LabAssignment(Base):
    __tablename__ = "lab_assignments"
    __table_args__ = (UniqueConstraint("lab_id", "student_id", name="uq_lab_student"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"))
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    assigned_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    lab: Mapped[Lab] = relationship(back_populates="assignments")
    student: Mapped[User] = relationship(back_populates="assignments", foreign_keys=[student_id])


class LabSession(Base):
    __tablename__ = "lab_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"))
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.running)
    access_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lab: Mapped[Lab] = relationship(back_populates="sessions")
    student: Mapped[User] = relationship(back_populates="sessions")


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    student: Mapped[User] = relationship(back_populates="scenarios")
    machines: Mapped[list[Machine]] = relationship(secondary=scenario_machines)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
