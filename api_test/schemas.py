from datetime import datetime
from pydantic import BaseModel, Field

from api_test.models import LabStatus, Role, SessionStatus


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
    os_type: str = Field(min_length=2, max_length=32)
    description: str = Field(default="", max_length=500)


class MachineRead(BaseModel):
    id: str
    name: str
    image_url: str
    os_type: str
    description: str
    approved: bool

    model_config = {"from_attributes": True}


class LabCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=1000)
    machine_ids: list[str] = Field(min_length=1)
    student_ids: list[str] = Field(default_factory=list)
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


class LabSessionRead(BaseModel):
    id: str
    lab_id: str
    student_id: str
    status: SessionStatus
    access_url: str | None
    started_at: datetime
    stopped_at: datetime | None

    model_config = {"from_attributes": True}
