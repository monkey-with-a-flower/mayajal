import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Table, Column, UniqueConstraint
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


lab_students = Table(
    "lab_students",
    Base.metadata,
    Column("lab_id", ForeignKey("labs.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


student_group_members = Table(
    "student_group_members",
    Base.metadata,
    Column("group_id", ForeignKey("student_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


lab_groups = Table(
    "lab_groups",
    Base.metadata,
    Column("lab_id", ForeignKey("labs.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("student_groups.id", ondelete="CASCADE"), primary_key=True),
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
    owned_groups: Mapped[list["StudentGroup"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    groups: Mapped[list["StudentGroup"]] = relationship(secondary=student_group_members, back_populates="students")


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    image_url: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(32), default="dockerhub")
    os_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(500), default="")
    hostname: Mapped[str | None] = mapped_column(String(160), nullable=True)
    command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    entrypoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    working_dir: Mapped[str | None] = mapped_column(String(300), nullable=True)
    run_as: Mapped[str | None] = mapped_column(String(100), nullable=True)
    restart_policy: Mapped[str] = mapped_column(String(32), default="unless-stopped")
    privileged: Mapped[bool] = mapped_column(Boolean, default=False)
    tty: Mapped[bool] = mapped_column(Boolean, default=True)
    stdin_open: Mapped[bool] = mapped_column(Boolean, default=False)
    ports: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    volumes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    environment: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    labels: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    dns: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    extra_hosts: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    cap_add: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    network_aliases: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    detection_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    labs: Mapped[list["Lab"]] = relationship(secondary=lab_machines, back_populates="machines")


class StudentGroup(Base):
    __tablename__ = "student_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner: Mapped[User] = relationship(back_populates="owned_groups")
    students: Mapped[list[User]] = relationship(secondary=student_group_members, back_populates="groups")
    labs: Mapped[list["Lab"]] = relationship(secondary=lab_groups, back_populates="groups")


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
    direct_students: Mapped[list[User]] = relationship(secondary=lab_students)
    groups: Mapped[list[StudentGroup]] = relationship(secondary=lab_groups, back_populates="labs")
    assignments: Mapped[list["LabAssignment"]] = relationship(back_populates="lab", cascade="all, delete-orphan")
    sessions: Mapped[list["LabSession"]] = relationship(back_populates="lab", cascade="all, delete-orphan")
    tasks: Mapped[list["LabTask"]] = relationship(back_populates="lab", cascade="all, delete-orphan", order_by="LabTask.position")


class LabTask(Base):
    __tablename__ = "lab_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"))
    prompt: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)

    lab: Mapped[Lab] = relationship(back_populates="tasks")


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
