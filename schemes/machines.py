from pydantic import BaseModel


class GetMachines(BaseModel):
    pass


class GetMachine(BaseModel):
    machineID: str
