from pydantic import BaseModel


class GetLabs(BaseModel):
    pass


class GetLab(BaseModel):
    labId: str