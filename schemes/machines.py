from pydantic import BaseModel
from typing import Literal



restartPolicy = Literal["Never","Always","On failure", "Unless stopped"]
osTypes = Literal["Linux","Windows","Others"]


class GetMachines(BaseModel):
    pass


class GetMachine(BaseModel):
    machineID: str

class CreateMachine(BaseModel):
    imageUrl: str
    volumes:dict | None
    env: dict | None
    restart_policy: restartPolicy | None
    commands: dict | None
    console: bool | None
    name: str
    os_type: osTypes
