from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_test.auth import require_roles
from api_test.config import AUTH_MODE
from api_test.database import get_db
from api_test.models import Lab, LabAssignment, LabSession, LabStatus, LabTask, Machine, Role, Scenario, SessionStatus, StudentGroup, SystemSetting, User
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
    student_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    publish: bool = True


class TeacherLabUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=1000)
    machine_ids: list[str] = Field(min_length=1)
    tasks: list[str] = Field(default_factory=list, max_length=12)
    student_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    publish: bool = True


class TeacherGroupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    student_ids: list[str] = Field(default_factory=list)


class MachineRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    image_url: str = Field(min_length=2, max_length=500)
    source_type: str = "dockerhub"
    os_type: str = Field(min_length=2, max_length=32)
    description: str = Field(default="", max_length=500)
    hostname: str | None = Field(default=None, max_length=160)
    command: str | None = Field(default=None, max_length=500)
    entrypoint: str | None = Field(default=None, max_length=500)
    working_dir: str | None = Field(default=None, max_length=300)
    run_as: str | None = Field(default=None, max_length=100)
    restart_policy: str = "unless-stopped"
    privileged: bool = False
    tty: bool = True
    stdin_open: bool = False
    ports: list[str] = Field(default_factory=list, max_length=24)
    volumes: list[str] = Field(default_factory=list, max_length=24)
    environment: dict[str, str] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)
    dns: list[str] = Field(default_factory=list, max_length=12)
    extra_hosts: list[str] = Field(default_factory=list, max_length=24)
    cap_add: list[str] = Field(default_factory=list, max_length=24)
    network_aliases: list[str] = Field(default_factory=list, max_length=12)
    detection_profile: str | None = Field(default=None, max_length=100)


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
        "source_type": machine.source_type,
        "description": machine.description,
        "hostname": machine.hostname,
        "command": machine.command,
        "entrypoint": machine.entrypoint,
        "working_dir": machine.working_dir,
        "run_as": machine.run_as,
        "restart_policy": machine.restart_policy,
        "privileged": machine.privileged,
        "tty": machine.tty,
        "stdin_open": machine.stdin_open,
        "ports": machine.ports or [],
        "volumes": machine.volumes or [],
        "environment": machine.environment or {},
        "labels": machine.labels or {},
        "dns": machine.dns or [],
        "extra_hosts": machine.extra_hosts or [],
        "cap_add": machine.cap_add or [],
        "network_aliases": machine.network_aliases or [],
        "detection_profile": machine.detection_profile,
        "added_by": "Platform" if machine.created_by_id else "System",
    }


def lab_payload(db: Session, lab: Lab, student_id: str | None = None) -> dict:
    if student_id:
        running = db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.student_id == student_id, LabSession.status == SessionStatus.running).first() is not None
    else:
        running = db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.status == SessionStatus.running).first() is not None
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
        "student_ids": [student.id for student in lab.direct_students],
        "group_ids": [group.id for group in lab.groups],
        "assigned_student_ids": [assignment.student_id for assignment in lab.assignments],
        "assigned_count": len(lab.assignments),
        "running_sessions": db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.status == SessionStatus.running).count(),
    }


def group_payload(group: StudentGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "student_ids": [student.id for student in group.students],
        "student_count": len(group.students),
        "lab_count": len(group.labs),
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


def resolve_students(db: Session, student_ids: list[str]) -> list[User]:
    if not student_ids:
        return []
    students = db.query(User).filter(User.id.in_(student_ids), User.role == Role.student).all()
    if len(students) != len(set(student_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each student assignment must target an existing student.")
    return students


def resolve_groups(db: Session, user: User, group_ids: list[str]) -> list[StudentGroup]:
    if not group_ids:
        return []
    query = db.query(StudentGroup).filter(StudentGroup.id.in_(group_ids))
    if user.role == Role.teacher:
        query = query.filter(StudentGroup.owner_id == user.id)
    groups = query.all()
    if len(groups) != len(set(group_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each group assignment must target a group you manage.")
    return groups


def managed_groups(db: Session, user: User) -> list[StudentGroup]:
    query = db.query(StudentGroup)
    if user.role == Role.teacher:
        query = query.filter(StudentGroup.owner_id == user.id)
    return query.order_by(StudentGroup.name).all()


def require_group_manager(user: User, group: StudentGroup) -> None:
    if user.role != Role.admin and group.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage student groups you created.")


def sync_lab_assignments(db: Session, lab: Lab, assigned_by_id: str) -> None:
    effective_students = {student.id: student for student in lab.direct_students}
    for group in lab.groups:
        effective_students.update({student.id: student for student in group.students})
    existing = {assignment.student_id: assignment for assignment in lab.assignments}
    for assignment in list(lab.assignments):
        if assignment.student_id not in effective_students:
            db.delete(assignment)
    for student_id in effective_students:
        if student_id not in existing:
            db.add(LabAssignment(lab_id=lab.id, student_id=student_id, assigned_by_id=assigned_by_id))


def replace_lab_assignments(db: Session, lab: Lab, user: User, student_ids: list[str], group_ids: list[str]) -> None:
    lab.direct_students = resolve_students(db, student_ids)
    lab.groups = resolve_groups(db, user, group_ids)
    db.flush()
    sync_lab_assignments(db, lab, user.id)


def student_progress_payload(db: Session, student: User) -> dict:
    assigned_labs = db.query(LabAssignment).filter(LabAssignment.student_id == student.id).count()
    running_labs = db.query(LabSession).filter(LabSession.student_id == student.id, LabSession.status == SessionStatus.running).count()
    progress = 100 if assigned_labs and running_labs == assigned_labs else 0
    return {"id": student.id, "name": student.name, "cohort": ", ".join(group.name for group in student.groups) or "Unassigned", "active_labs": assigned_labs, "running_labs": running_labs, "progress": progress}


def running_session_payload(session: LabSession) -> dict:
    return {
        "id": session.id,
        "lab_id": session.lab_id,
        "lab": session.lab.name,
        "student_id": session.student_id,
        "student": session.student.name,
        "status": session.status.value,
        "started_at": session.started_at.isoformat(),
    }


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
    running_sessions = db.query(LabSession).filter(LabSession.status == SessionStatus.running)
    if user.role == Role.teacher:
        running_sessions = running_sessions.join(Lab).filter(Lab.owner_id == user.id)
    return {
        "labs": [lab_payload(db, lab, user.id) for lab in labs],
        "machines": [machine_payload(machine) for machine in db.query(Machine).filter(Machine.approved.is_(True)).order_by(Machine.name).all()],
        "students": [student_progress_payload(db, student) for student in students],
        "groups": [group_payload(group) for group in managed_groups(db, user)],
        "metrics": {"students": len(students), "labs": len(labs), "running_sessions": running_sessions.count()},
        "reviews": [{"id": "review-" + assignment.id, "student": assignment.student.name, "lab": assignment.lab.name, "state": "Ready for review"} for lab in labs for assignment in lab.assignments],
    }


@router.post("/teacher/labs", status_code=status.HTTP_201_CREATED)
def create_teacher_lab(payload: TeacherLabRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    machines = approved_machines(db, payload.machine_ids)
    lab = Lab(name=payload.name, description=payload.description, status=LabStatus.published if payload.publish else LabStatus.draft, owner_id=user.id, machines=machines)
    replace_lab_tasks(lab, payload.tasks)
    db.add(lab)
    db.flush()
    replace_lab_assignments(db, lab, user, payload.student_ids, payload.group_ids)
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
    replace_lab_assignments(db, lab, user, payload.student_ids, payload.group_ids)
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


@router.post("/teacher/groups", status_code=status.HTTP_201_CREATED)
def create_teacher_group(payload: TeacherGroupRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    students = resolve_students(db, payload.student_ids)
    group = StudentGroup(name=payload.name.strip(), owner_id=user.id, students=students)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group_payload(group)


@router.patch("/teacher/groups/{group_id}")
def update_teacher_group(group_id: str, payload: TeacherGroupRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    group = db.get(StudentGroup, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student group not found.")
    require_group_manager(user, group)
    group.name = payload.name.strip()
    group.students = resolve_students(db, payload.student_ids)
    db.flush()
    for lab in list(group.labs):
        sync_lab_assignments(db, lab, user.id)
    db.commit()
    db.refresh(group)
    return group_payload(group)


@router.delete("/teacher/groups/{group_id}")
def delete_teacher_group(group_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    group = db.get(StudentGroup, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student group not found.")
    require_group_manager(user, group)
    affected_labs = list(group.labs)
    for lab in affected_labs:
        lab.groups = [item for item in lab.groups if item.id != group.id]
        sync_lab_assignments(db, lab, user.id)
    db.delete(group)
    db.commit()
    return {"id": group_id, "message": "Student group removed."}


@router.post("/teacher/reviews/{review_id}")
def complete_review(review_id: str, user: User = Depends(require_roles(Role.teacher, Role.admin))):
    return {"id": review_id, "message": "Feedback recorded."}


@router.get("/admin/dashboard")
def admin_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    running_sessions = db.query(LabSession).filter(LabSession.status == SessionStatus.running).all()
    students = db.query(User).filter(User.role == Role.student).count()
    teachers = db.query(User).filter(User.role == Role.teacher).count()
    return {
        "labs": [lab_payload(db, lab, user.id) for lab in db.query(Lab).all()],
        "machines": [machine_payload(machine) for machine in db.query(Machine).order_by(Machine.name).all()],
        "users": [{"id": member.id, "name": member.name, "username": member.username or member.email, "role": member.role.value, "status": "Active"} for member in db.query(User).order_by(User.name).all()],
        "groups": [group_payload(group) for group in db.query(StudentGroup).order_by(StudentGroup.name).all()],
        "running_sessions": [running_session_payload(session) for session in running_sessions],
        "metrics": {"students": students, "teachers": teachers, "labs": db.query(Lab).count(), "running_sessions": len(running_sessions)},
        "settings": [{"id": setting.id, "label": setting.label, "enabled": setting.enabled} for setting in db.query(SystemSetting).order_by(SystemSetting.id).all()],
        "health": [{"name": "Core database", "value": "Healthy"}, {"name": "Machine catalogue", "value": str(db.query(Machine).count()) + " images"}, {"name": "Running lab sessions", "value": str(len(running_sessions))}, {"name": "Access policies", "value": "Enforced"}],
    }


@router.post("/admin/machines", status_code=status.HTTP_201_CREATED)
def create_admin_machine(payload: MachineRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    if db.query(Machine).filter(Machine.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A machine with this name already exists.")
    machine = Machine(**payload.model_dump(), created_by_id=user.id, approved=True)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine_payload(machine)


@router.patch("/admin/machines/{machine_id}")
def update_admin_machine(machine_id: str, payload: MachineRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")
    duplicate = db.query(Machine).filter(Machine.name == payload.name, Machine.id != machine_id).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A machine with this name already exists.")
    for key, value in payload.model_dump().items():
        setattr(machine, key, value)
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
