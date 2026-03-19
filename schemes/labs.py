from pydantic import BaseModel
from typing import Any


class GetLabs(BaseModel):
    pass


class GetLab(BaseModel):
    labId: str

class CreateLab(BaseModel):
    name: str
    description: str | None
    machines: dict[str,Any] 
