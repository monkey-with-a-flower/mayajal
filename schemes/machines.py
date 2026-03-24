from pydantic import BaseModel
from typing import Literal,Optional



restartPolicy = Literal["no","always","on-failure", "unless-stopped"]
osTypes = Literal["Linux","Windows","Others"]


class GetMachines(BaseModel):
    pass


class GetMachine(BaseModel):
    machineID: str

class CreateMachine(BaseModel):
    imageUrl: str
    volumes:Optional[dict[str,str]] = None
    env: Optional[dict[str,str]] = None
    restart_policy: Optional[restartPolicy] = "unless-stopped"
    commands: Optional[dict[str,str] ] = None
    console: Optional[bool ] = True
    name: str
    os_type: osTypes