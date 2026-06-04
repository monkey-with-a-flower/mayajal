from pathlib import Path

from fastapi import APIRouter,HTTPException,status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from api.config import ASSETS_DIR, LAB_DIR
from api.get_current_user import get_current_user
from api.db import get_db
from api.models.labs import Lab
from api.models.machines import Machine
from api.models.users import User
from api.schemes.labs import CreateLab
from api.services.labs import getPeerConfig, startLab,stop
from jinja2 import Template
router = APIRouter()


def resolve_machines(machine_ids: list[str], db: Session) -> list[Machine]:
    machines = db.query(Machine).filter(Machine.id.in_(machine_ids)).all()
    found_ids = {machine.id for machine in machines}
    missing_ids = [machine_id for machine_id in machine_ids if machine_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown machine IDs: {', '.join(missing_ids)}",
        )
    return machines


@router.post("/",status_code=status.HTTP_201_CREATED)
def createLab(payload:CreateLab,db:Session = Depends(get_db),current_user:User = Depends(get_current_user)):
    if payload:
        machines = resolve_machines(payload.machines, db)
        try: 
            lab = Lab(
                name = payload.name,
                description = payload.description,
                machines = machines,
                owner_id = current_user.id
            )
            db.add(lab)
            db.flush()
            labdir = Path(f"{LAB_DIR}/{lab.id}")
            labdir.mkdir(parents= True,exist_ok=False)
            envTemplate = Template(Path(f"{ASSETS_DIR}/env.j2").read_text())
            env = envTemplate.render(
                LABID = lab.id,
                PEERS = lab.owner_id,
                MASTERURL = "192.168.1.14",
                LABPORT = "51820"
            )
            Path(f"{labdir}/.env").write_text(env)
            db.commit()
            db.refresh(lab)
            return lab
        except Exception as e:
            db.rollback()
            raise HTTPException (
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail= str(e)
            )
   
    else:
        raise HTTPException (
            status_code=status.HTTP_400_BAD_REQUEST
        )


@router.get("/",status_code=status.HTTP_200_OK)
def getLabs(db:Session = Depends(get_db), current_user:User = Depends(get_current_user)):
    if current_user:
        try:
            labs = db.query(Lab).filter(Lab.owner_id == current_user.id).all()
            return labs
        except Exception as e:
            raise HTTPException(
                status_code= status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        

@router.get("/{labId}",status_code=status.HTTP_200_OK)
def getLab(labId: str, db:Session = Depends(get_db),current_user:User = Depends(get_current_user)):
    lab = db.query(Lab).filter(Lab.id == labId, Lab.owner_id == current_user.id).first()
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    return lab

@router.patch("/{labId}",status_code=status.HTTP_200_OK)
def patchLab(labId,payload:CreateLab,db:Session = Depends(get_db),current_user:User = Depends(get_current_user)):
    if payload:
        lab = db.query(Lab).filter(Lab.id == labId).first()
        if lab is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
        if lab.owner_id == current_user.id:
            lab.name = payload.name
            lab.description = payload.description
            lab.machines = resolve_machines(payload.machines, db)
            try: 
                db.commit()
                db.refresh(lab)
                return lab
            except Exception as e:
                db.rollback()
                raise HTTPException (
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail= str(e)
                )
        else:
            raise HTTPException(
                status_code= status.HTTP_403_FORBIDDEN,
                detail="Not Allowed!"
            )
     
@router.delete("/{labId}")
def deleteLab(labId: str,db:Session = Depends(get_db),current_user:User = Depends(get_current_user)):
    if labId:
        lab = db.query(Lab).filter(Lab.id == labId, Lab.owner_id == current_user.id).first()
        if lab is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
        try:
            db.delete(lab)
            db.commit()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return {"deleted": labId}
    

@router.get("/{labId}/start")
async def start_lab(labId: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lab = db.query(Lab).filter(Lab.id == labId, Lab.owner_id == current_user.id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")

    return StreamingResponse(startLab(lab), media_type="text/plain")


# @router.get("/{labId}/start")
# def stratlab(labId: str,db:Session = Depends(get_db)):
#     if labId:
#         try:
#             lab = db.query(Lab).filter(Lab.id == labId).first()
#             return StreamingResponse(startLab(lab=lab),media_type="text/plain")
#         except Exception as e:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=str(e)
#             )
        
#     else:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST
#         )
    
@router.get("/{labId}/config")
def getConfig(labId: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lab = db.query(Lab).filter(Lab.id == labId, Lab.owner_id == current_user.id).first()
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    try:
        return getPeerConfig(lab)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
@router.get("/{labId}/stop")
async def stopLab(labId: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lab = db.query(Lab).filter(Lab.id == labId, Lab.owner_id == current_user.id).first()
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found")
    return StreamingResponse(stop(labId), media_type="text/plain")
