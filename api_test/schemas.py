from datetime import datetime
from pydantic import BaseModel, Field

from api_test.models import LabStatus, Role, SessionStatus

MachineSource = str
RestartPolicy = str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: str
    username: str | None
    name: str
    email: str
    role: Role

    model_config = {"from_attributes": True}


class MachineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    image_url: str = Field(min_length=3, max_length=500)
    source_type: MachineSource = "dockerhub"
    os_type: str = Field(min_length=2, max_length=32)
    description: str = Field(default="", max_length=500)
    hostname: str | None = Field(default=None, max_length=160)
    command: str | None = Field(default=None, max_length=500)
    entrypoint: str | None = Field(default=None, max_length=500)
    working_dir: str | None = Field(default=None, max_length=300)
    run_as: str | None = Field(default=None, max_length=100)
    restart_policy: RestartPolicy = "unless-stopped"
    privileged: bool = False
    tty: bool = True
    stdin_open: bool = False
    ports: list[str] = Field(default_factory=list, max_length=24)
    volumes: list[str] = Field(default_factory=list, max_length=24)
    environment: dict[str, str] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)
    dns: list[str] = Field(default_factory=list, max_length=12)
    extra_hosts: list[str] = Field(default_factory=list, max_length=24)
    cap_add: list[str] = Field(default_factory=list, max_length=24)
    network_aliases: list[str] = Field(default_factory=list, max_length=12)


class MachineRead(BaseModel):
    id: str
    name: str
    image_url: str
    source_type: str
    os_type: str
    description: str
    hostname: str | None
    command: str | None
    entrypoint: str | None
    working_dir: str | None
    run_as: str | None
    restart_policy: str
    privileged: bool
    tty: bool
    stdin_open: bool
    ports: list[str] | None
    volumes: list[str] | None
    environment: dict[str, str] | None
    labels: dict[str, str] | None
    dns: list[str] | None
    extra_hosts: list[str] | None
    cap_add: list[str] | None
    network_aliases: list[str] | None
    approved: bool

    model_config = {"from_attributes": True}


class LabCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=1000)
    machine_ids: list[str] = Field(min_length=1)
    student_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    publish: bool = True


class AssignmentCreate(BaseModel):
    student_ids: list[str] = Field(min_length=1)


class LabRead(BaseModel):
    id: str
    name: str
    description: str
    status: LabStatus
    owner_id: str
    machine_ids: list[str]
    student_ids: list[str]
    group_ids: list[str]
    assigned_student_ids: list[str]


class LabSessionRead(BaseModel):
    id: str
    lab_id: str
    student_id: str
    status: SessionStatus
    access_url: str | None
    started_at: datetime
    stopped_at: datetime | None

    model_config = {"from_attributes": True}
