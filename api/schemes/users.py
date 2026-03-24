from pydantic import BaseModel


class GetUser(BaseModel):
    pass

class ModifyUser(BaseModel):
    name: str
    email: str

