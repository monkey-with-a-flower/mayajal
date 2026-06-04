from fastapi import APIRouter, Depends,HTTPException, status
from sqlalchemy.orm import Session

from api.config import ASSETS_DIR, MACHINE_DIR
from api.db import get_db
from api.get_current_user import get_current_user
from api.models.machines import Machine
from api.models.users import User
from api.schemes.machines import CreateMachine
from pathlib import Path
from jinja2 import Template

router = APIRouter()


def write_compose_file(machine: Machine) -> None:
    template_path = Path(f"{ASSETS_DIR}/machine_template.yml.j2")
    output_path = Path(f"{MACHINE_DIR}/{machine.id}.yml")
    template = Template(template_path.read_text())
    rendered = template.render(
        image=machine.imageUrl,
        name=machine.name,
        env=machine.env,
        restart_policy=machine.restart_policy,
        commands=machine.commands,
        tty=str(machine.console).lower(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered)


@router.get("/")
def getAllMachines(db:Session = Depends (get_db)):
    machines = db.query(Machine).all()
    return machines

@router.get("/{machineId}")
def getMachine(machineId: str, db:Session = Depends (get_db)):
    machine = db.query(Machine).filter(Machine.id == machineId).first()
    return machine

@router.post("/", status_code=status.HTTP_201_CREATED)
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
        db.flush()
        write_compose_file(machine)
        db.commit()
        db.refresh(machine)
        return machine


    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

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
            write_compose_file(machine)
            return machine
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
def deleteMachine(machineId: str,db:Session = Depends(get_db)):
    if machineId:
        machine = db.query(Machine).filter(Machine.id == machineId).first()
        if machine is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
        try:
            db.delete(machine)
            db.commit()
            Path(f"{MACHINE_DIR}/{machineId}.yml").unlink(missing_ok=True)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return {"deleted": machineId}
    
