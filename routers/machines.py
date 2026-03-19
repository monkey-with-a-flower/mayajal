from fastapi import APIRouter, Depends,HTTPException, status
from sqlalchemy.orm import Session

from api.db import get_db
from api.get_current_user import get_current_user
from api.models.machines import Machine
from api.models.users import User
from api.schemes.machines import CreateMachine


router = APIRouter()

@router.get("/")
def getAllMachines(db:Session = Depends (get_db)):
    machines = db.query(Machine).all()
    return machines

@router.get("/{machineId}")
def getMachine(machineId: str, db:Session = Depends (get_db)):
    machine = db.query(Machine).filter(Machine.id == machineId).first()
    return machine

@router.post("/")
def createMachine(payload:CreateMachine, db:Session = Depends(get_db)):
    if payload:
        machine = Machine(
            imageUrl = payload.imageUrl,
            volumes = payload.volumes,
            env = payload.env,
            restart_policy = payload.restart_policy,
            commands = payload.commands,
            console = payload.console,
            name = payload.name,
            os_type = payload.os_type
        )
    else: 
        raise HTTPException(
            status_code= status.HTTP_400_BAD_REQUEST
        )
    try:
        db.add(machine)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ))

@router.patch("/{machineId}")
def patchMachine(machineId: str,payload: CreateMachine, db: Session = Depends(get_db)):
    machine:Machine = db.query(Machine).filter(Machine.id == machineId).first()
    
    if machine:
        machine.imageUrl = payload.imageUrl
        machine.volumes = payload.volumes
        machine.env=payload.env
        machine.restart_policy = payload.restart_policy
        machine.commands = payload.commands
        machine.console = payload.console
        machine.name = payload.name
        machine.os_type = payload.os_type
        try: 
            db.commit()
            db.refresh(machine)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    else:
        raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Machine not found"
        )



@router.delete("/{machineId}")
def deleteMachine(machineID: str,db:Session = Depends(get_db)):
    if machineID:
        try:
            machine = db.query(Machine).filter(Machine.id == machineID).first()
            db.delete(machine)
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