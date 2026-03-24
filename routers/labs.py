from pathlib import Path

from fastapi import APIRouter,HTTPException,status, Depends
from sqlalchemy.orm import Session
from api.config import ASSETS_DIR, LAB_DIR
from api.get_current_user import get_current_user
from api.db import get_db
from api.models.labs import Lab
from api.models.machines import Machine
from api.models.users import User
from api.schemes.labs import CreateLab
from api.services.labs import startLab
import os
from jinja2 import Template
router = APIRouter()

   
@router.post("/",status_code=status.HTTP_201_CREATED)
def createLab(payload:CreateLab,db:Session = Depends(get_db),current_user:User = Depends(get_current_user)):
    if payload:
        try: 
            machines = []
            for machine in payload.machines:
                print (machine)
                machines.append(db.query(Machine).filter(Machine.id == machine).first())
            lab = Lab(
                name = payload.name,
                description = payload.description,
                machines = machines,
                owner_id = current_user.id
            )
            db.add(lab)
            db.commit()
            db.refresh(lab)
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
    try:
        lab = db.query(Lab).filter(Lab.id == labId and Lab.owner_id == current_user.id).first()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            details= "Lab not found"
        )
    return lab

@router.patch("/{labId}",status_code=status.HTTP_200_OK)
def patchLab(labId,payload:CreateLab,db:Session = Depends(get_db),current_user:User = Depends(get_current_user)):
    if payload:
        lab = db.query(Lab).filter(Lab.id == labId).first()
        if lab.owner_id == current_user.id:
            lab.name = payload.name
            lab.description = payload.description
            lab.machines = payload.machines
            try: 
                db.commit()
                db.refresh(lab)
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
        try:
            lab = db.query(Lab).filter(Lab.owner_id == current_user.id).first()
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
    




@router.get("/{labId}/start")
def stratlab(labId: str,db:Session = Depends(get_db),current_user:User = Depends(get_current_user)):
    if labId:
        try:
            lab = db.query(Lab).filter(Lab.owner_id == current_user.id).first()
            return startLab(lab=lab)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST
        )