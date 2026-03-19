from contextlib import asynccontextmanager

from fastapi import FastAPI
from api.db import Base,engine
from api.routers.labs import router as labRouter
from api.routers.machines import router as machinesRouter
from api.routers.users import router as usersRouter





@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)


app.include_router( labRouter, prefix="/labs",tags=["Labs"])
app.include_router( machinesRouter, prefix="/machines",tags=["Machines"])
app.include_router( usersRouter, prefix="/me",tags=["Users"])
