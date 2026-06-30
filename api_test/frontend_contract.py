from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_test.auth import require_roles
from api_test.config import AUTH_MODE
from api_test.database import get_db
from api_test.models import Lab, LabAssignment, LabSession, LabStatus, LabTask, Machine, Role, Scenario, SessionStatus, SystemSetting, User
from api_test.services import require_lab_manager, start_session

router = APIRouter()


class ScenarioRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    machine_ids: list[str] = Field(min_length=1)


class TeacherLabRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=1000)
    machine_ids: list[str] = Field(min_length=1)
    tasks: list[str] = Field(default_factory=list, max_length=12)
    publish: bool = True


class TeacherLabUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=1000)
    machine_ids: list[str] = Field(min_length=1)
    tasks: list[str] = Field(default_factory=list, max_length=12)
    publish: bool = True


class MachineRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    os_type: str = Field(min_length=2, max_length=32)


class RoleRequest(BaseModel):
    role: Role


class SettingRequest(BaseModel):
    enabled: bool


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper() or "MA"


def user_payload(user: User) -> dict:
    return {"id": user.id, "name": user.name, "role": user.role.value, "initials": initials(user.name)}


def machine_payload(machine: Machine) -> dict:
    return {
        "id": machine.id,
        "name": machine.name,
        "os_type": machine.os_type,
        "imageUrl": machine.image_url,
        "description": machine.description,
        "added_by": "Platform" if machine.created_by_id else "System",
    }


def lab_payload(db: Session, lab: Lab, student_id: str | None = None) -> dict:
    running = False
    if student_id:
        running = db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.student_id == student_id, LabSession.status == SessionStatus.running).first() is not None
    return {
        "id": lab.id,
        "name": lab.name,
        "description": lab.description,
        "status": "running" if running else "ready" if lab.status == LabStatus.published else "locked",
        "owner": lab.owner.name,
        "level": "Beginner",
        "runtime": "45 min",
        "progress": 35 if running else 0,
        "next_step": "Download the VPN config and connect with WireGuard" if running else "Start the lab when you are ready",
        "machine_ids": [machine.id for machine in lab.machines],
        "tasks": [task.prompt for task in lab.tasks],
    }


def scenario_payload(scenario: Scenario, updated_at: str | None = None) -> dict:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "status": "saved",
        "machine_ids": [machine.id for machine in scenario.machines],
        "updated_at": updated_at or scenario.updated_at.strftime("%b %d, %H:%M"),
    }


def approved_machines(db: Session, machine_ids: list[str]) -> list[Machine]:
    machines = db.query(Machine).filter(Machine.id.in_(machine_ids), Machine.approved.is_(True)).all()
    if len(machines) != len(set(machine_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each lab machine must exist and be approved.")
    return machines


def replace_lab_tasks(lab: Lab, prompts: list[str]) -> None:
    lab.tasks = [LabTask(prompt=prompt.strip(), position=index) for index, prompt in enumerate(prompts) if prompt.strip()]


@router.get("/student/dashboard")
def student_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    assignments = db.query(Lab).join(LabAssignment).filter(LabAssignment.student_id == user.id, Lab.status == LabStatus.published).all()
    scenarios = db.query(Scenario).filter(Scenario.student_id == user.id).order_by(Scenario.updated_at.desc()).all()
    return {
        "student": user_payload(user),
        "assignments": [lab_payload(db, lab, user.id) for lab in assignments],
        "machines": [machine_payload(machine) for machine in db.query(Machine).filter(Machine.approved.is_(True)).order_by(Machine.name).all()],
        "scenarios": [scenario_payload(scenario) for scenario in scenarios],
        "activity": [{"id": "assignment-" + lab.id, "title": "Lab assigned", "detail": lab.name, "when": "Available now"} for lab in assignments],
    }


@router.post("/student/scenarios", status_code=status.HTTP_201_CREATED)
def save_scenario(payload: ScenarioRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    machines = db.query(Machine).filter(Machine.id.in_(payload.machine_ids), Machine.approved.is_(True)).all()
    if len(machines) != len(set(payload.machine_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each scenario machine must exist and be approved.")
    scenario = Scenario(name=payload.name, student_id=user.id, machines=machines)
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario_payload(scenario, "Just now")


@router.patch("/student/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, payload: ScenarioRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.student_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    machines = db.query(Machine).filter(Machine.id.in_(payload.machine_ids), Machine.approved.is_(True)).all()
    if len(machines) != len(set(payload.machine_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each scenario machine must exist and be approved.")
    scenario.name = payload.name
    scenario.machines = machines
    db.commit()
    db.refresh(scenario)
    return scenario_payload(scenario, "Just now")


@router.delete("/student/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.student_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    db.delete(scenario)
    db.commit()
    return {"id": scenario_id, "message": "Scenario removed from your workspace."}


@router.get("/teacher/dashboard")
def teacher_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    labs = db.query(Lab).filter(Lab.owner_id == user.id).all() if user.role == Role.teacher else db.query(Lab).all()
    students = db.query(User).filter(User.role == Role.student).order_by(User.name).all()
    return {
        "labs": [lab_payload(db, lab) for lab in labs],
        "machines": [machine_payload(machine) for machine in db.query(Machine).filter(Machine.approved.is_(True)).order_by(Machine.name).all()],
        "students": [{"id": student.id, "name": student.name, "cohort": "Security Foundations", "active_labs": db.query(LabAssignment).filter(LabAssignment.student_id == student.id).count(), "progress": 0} for student in students],
        "reviews": [{"id": "review-" + assignment.id, "student": assignment.student.name, "lab": assignment.lab.name, "state": "Ready for review"} for lab in labs for assignment in lab.assignments],
    }


@router.post("/teacher/labs", status_code=status.HTTP_201_CREATED)
def create_teacher_lab(payload: TeacherLabRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    machines = approved_machines(db, payload.machine_ids)
    lab = Lab(name=payload.name, description=payload.description, status=LabStatus.published if payload.publish else LabStatus.draft, owner_id=user.id, machines=machines)
    replace_lab_tasks(lab, payload.tasks)
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab_payload(db, lab)


@router.patch("/teacher/labs/{lab_id}")
def update_teacher_lab(lab_id: str, payload: TeacherLabUpdateRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_lab_manager(user, lab)
    machines = approved_machines(db, payload.machine_ids)
    lab.name = payload.name
    lab.description = payload.description
    lab.machines = machines
    replace_lab_tasks(lab, payload.tasks)
    lab.status = LabStatus.published if payload.publish else LabStatus.draft
    db.commit()
    db.refresh(lab)
    return lab_payload(db, lab)


@router.delete("/teacher/labs/{lab_id}")
def delete_teacher_lab(lab_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_lab_manager(user, lab)
    db.delete(lab)
    db.commit()
    return {"id": lab_id, "message": "Lab removed from the teacher catalogue."}


@router.post("/teacher/reviews/{review_id}")
def complete_review(review_id: str, user: User = Depends(require_roles(Role.teacher, Role.admin))):
    return {"id": review_id, "message": "Feedback recorded."}


@router.get("/admin/dashboard")
def admin_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    return {
        "labs": [lab_payload(db, lab) for lab in db.query(Lab).all()],
        "machines": [machine_payload(machine) for machine in db.query(Machine).order_by(Machine.name).all()],
        "users": [{"id": member.id, "name": member.name, "username": member.username or member.email, "role": member.role.value, "status": "Active"} for member in db.query(User).order_by(User.name).all()],
        "settings": [{"id": setting.id, "label": setting.label, "enabled": setting.enabled} for setting in db.query(SystemSetting).order_by(SystemSetting.id).all()],
        "health": [{"name": "Core database", "value": "Healthy"}, {"name": "Machine catalogue", "value": str(db.query(Machine).count()) + " images"}, {"name": "Access policies", "value": "Enforced"}],
    }


@router.post("/admin/machines", status_code=status.HTTP_201_CREATED)
def create_admin_machine(payload: MachineRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    if db.query(Machine).filter(Machine.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A machine with this name already exists.")
    machine = Machine(name=payload.name, image_url="registry.mayajal.local/" + payload.name.lower().replace(" ", "-"), os_type=payload.os_type, description="Approved machine image ready for lab use.", created_by_id=user.id, approved=True)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine_payload(machine)


@router.patch("/admin/users/{user_id}/role")
def change_role(user_id: str, payload: RoleRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    if AUTH_MODE == "entra":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Roles are managed by Microsoft Entra app roles.")
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    target.role = payload.role
    db.commit()
    return {"id": target.id, "role": target.role.value, "message": target.name + " now has " + target.role.value + " access."}


@router.patch("/admin/settings/{setting_id}")
def change_setting(setting_id: str, payload: SettingRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    setting = db.get(SystemSetting, setting_id)
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found.")
    setting.enabled = payload.enabled
    db.commit()
    return {"id": setting.id, "enabled": setting.enabled, "message": setting.label + " updated."}
