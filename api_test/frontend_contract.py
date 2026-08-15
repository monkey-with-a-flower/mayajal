from datetime import datetime, timezone
import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_test.auth import require_roles
from api_test.config import AUTH_MODE, IMPORTED_MACHINES_DIR
from api_test.database import get_db
from api_test.models import Lab, LabAnswer, LabAssignment, LabSession, LabStatus, LabSubmission, LabTask, Machine, MachineImportVersion, Role, Scenario, ScenarioSession, SessionStatus, StudentGroup, SystemSetting, User
from api_test.services import require_lab_manager, require_student_access, start_session
from api_test.machine_import import MachineImportError, discover_machine_folders, download_github_archive, install_machine_archive, machine_content_digest

router = APIRouter()


class ScenarioRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    machine_ids: list[str] = Field(min_length=1)


class LabAnswersRequest(BaseModel):
    answers: dict[str, str]


class TeacherTaskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    grading_type: str = Field(default="manual", pattern="^(exact|contains|regex|manual)$")
    expected_answer: str | None = Field(default=None, max_length=500)
    points: int = Field(default=1, ge=1, le=100)


class FinalizeSubmissionRequest(BaseModel):
    final_score: int | None = Field(default=None, ge=0)
    feedback: str = Field(default="", max_length=2000)


class TeacherLabRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=1000)
    machine_ids: list[str] = Field(min_length=1)
    tasks: list[str | TeacherTaskRequest] = Field(default_factory=list, max_length=12)
    student_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    publish: bool = True


class TeacherLabUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=1000)
    machine_ids: list[str] = Field(min_length=1)
    tasks: list[str | TeacherTaskRequest] = Field(default_factory=list, max_length=12)
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
    attachment: str | None = Field(default=None, max_length=500)
    attachments: list[str] = Field(default_factory=list, max_length=50)
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
    memory_limit: str = Field(default="512m", pattern=r"^[1-9]\d*(m|g)$")
    cpu_limit: float = Field(default=1.0, ge=0.1, le=16)


class GitHubMachineImportRequest(BaseModel):
    repository_url: str = Field(min_length=20, max_length=500)
    ref: str = Field(default="main", min_length=1, max_length=200)
    machine_path: str = Field(min_length=1, max_length=500)


class GitHubRepositoryRequest(BaseModel):
    repository_url: str = Field(min_length=20, max_length=500)
    ref: str = Field(default="main", min_length=1, max_length=200)


class RoleRequest(BaseModel):
    role: Role


class SettingRequest(BaseModel):
    enabled: bool


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper() or "MA"


def user_payload(user: User) -> dict:
    return {"id": user.id, "name": user.name, "role": user.role.value, "initials": initials(user.name)}


def machine_payload(machine: Machine) -> dict:
    latest_version = machine.import_versions[-1] if machine.import_versions else None
    return {
        "id": machine.id,
        "name": machine.name,
        "os_type": machine.os_type,
        "imageUrl": machine.image_url,
        "source_type": machine.source_type,
        "description": machine.description,
        "attachment": machine.attachment,
        "attachments": machine.attachments or ([machine.attachment] if machine.attachment else []),
        "repository_url": machine.repository_url,
        "repository_ref": machine.repository_ref,
        "repository_path": machine.repository_path,
        "detection_rules": machine.detection_rules or {},
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
        "memory_limit": machine.memory_limit,
        "cpu_limit": machine.cpu_limit,
        "added_by": "Platform" if machine.created_by_id else "System",
        "source_digest": latest_version.source_digest if latest_version else None,
        "import_version": len(machine.import_versions),
        "last_imported_at": latest_version.imported_at.isoformat() if latest_version else None,
    }


def lab_payload(db: Session, lab: Lab, student_id: str | None = None, include_grading: bool = False) -> dict:
    if student_id:
        running = db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.student_id == student_id, LabSession.status == SessionStatus.running).first() is not None
    else:
        running = db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.status == SessionStatus.running).first() is not None
    answers = {
        answer.task_id: answer.answer
        for answer in db.query(LabAnswer).filter(LabAnswer.lab_id == lab.id, LabAnswer.student_id == student_id).all()
    } if student_id else {}
    latest_submission = (
        db.query(LabSubmission)
        .filter(LabSubmission.lab_id == lab.id, LabSubmission.student_id == student_id)
        .order_by(LabSubmission.submitted_at.desc())
        .first()
    ) if student_id else None
    payload = {
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
        "questions": [{"id": task.id, "prompt": task.prompt, "answer": answers.get(task.id, "")} for task in lab.tasks],
        "student_ids": [student.id for student in lab.direct_students],
        "group_ids": [group.id for group in lab.groups],
        "assigned_student_ids": [assignment.student_id for assignment in lab.assignments],
        "assigned_count": len(lab.assignments),
        "running_sessions": db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.status == SessionStatus.running).count(),
        "submission_status": latest_submission.status if latest_submission else None,
        "score": latest_submission.final_score if latest_submission and latest_submission.status == "finalized" else latest_submission.auto_score if latest_submission else None,
        "max_score": latest_submission.max_score if latest_submission else sum(task.points for task in lab.tasks),
    }
    if include_grading:
        payload["grading_tasks"] = [
            {"id": task.id, "prompt": task.prompt, "grading_type": task.grading_type, "expected_answer": task.expected_answer or "", "points": task.points}
            for task in lab.tasks
        ]
    return payload


def group_payload(group: StudentGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "student_ids": [student.id for student in group.students],
        "student_count": len(group.students),
        "lab_count": len(group.labs),
    }


def scenario_payload(scenario: Scenario, updated_at: str | None = None) -> dict:
    running_session = next((session for session in scenario.sessions if session.status == SessionStatus.running), None)
    return {
        "id": scenario.id,
        "name": scenario.name,
        "status": "running" if running_session else "saved",
        "running_session_id": running_session.id if running_session else None,
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


def replace_lab_tasks(lab: Lab, tasks: list[str | TeacherTaskRequest]) -> None:
    configured: list[LabTask] = []
    for index, item in enumerate(tasks):
        task = TeacherTaskRequest(prompt=item) if isinstance(item, str) else item
        prompt = task.prompt.strip()
        expected = (task.expected_answer or "").strip() or None
        if task.grading_type != "manual" and expected is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Automatically graded questions require an expected answer or pattern.")
        configured.append(LabTask(prompt=prompt, position=index, grading_type=task.grading_type, expected_answer=expected, points=task.points))
    lab.tasks = configured


def grade_answer(task: LabTask, answer: str) -> tuple[bool | None, int]:
    submitted = answer.strip()
    expected = (task.expected_answer or "").strip()
    if task.grading_type == "manual":
        return None, 0
    if task.grading_type == "exact":
        correct = submitted == expected
    elif task.grading_type == "contains":
        correct = expected.casefold() in submitted.casefold()
    elif task.grading_type == "regex":
        try:
            correct = re.search(expected, submitted) is not None
        except re.error:
            correct = False
    else:
        correct = False
    return correct, task.points if correct else 0


def submission_payload(submission: LabSubmission, include_answers: bool = False) -> dict:
    results = []
    for result in submission.results or []:
        item = {key: value for key, value in result.items() if key != "expected_answer"}
        if not include_answers:
            item.pop("answer", None)
        results.append(item)
    return {
        "id": submission.id,
        "lab_id": submission.lab_id,
        "lab": submission.lab.name,
        "student_id": submission.student_id,
        "student": submission.student.name,
        "status": submission.status,
        "state": submission.status == "awaiting_review" and f"Automatic score {submission.auto_score}/{submission.max_score}" or "Finalized",
        "auto_score": submission.auto_score,
        "max_score": submission.max_score,
        "final_score": submission.final_score,
        "feedback": submission.feedback or "",
        "submitted_at": submission.submitted_at.isoformat(),
        "finalized_at": submission.finalized_at.isoformat() if submission.finalized_at else None,
        "results": results,
    }


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


@router.put("/student/labs/{lab_id}/answers")
def save_lab_answers(lab_id: str, payload: LabAnswersRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    lab = db.get(Lab, lab_id)
    if lab is None or lab.status != LabStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published lab not found.")
    require_student_access(db, user, lab)
    tasks = {task.id: task for task in lab.tasks}
    if not set(payload.answers).issubset(tasks):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answers must target questions in this lab.")
    existing = {
        answer.task_id: answer
        for answer in db.query(LabAnswer).filter(LabAnswer.lab_id == lab.id, LabAnswer.student_id == user.id).all()
    }
    for task_id, value in payload.answers.items():
        answer_text = value.strip()
        if len(answer_text) > 4000:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Each answer must be 4000 characters or fewer.")
        if task_id in existing:
            existing[task_id].answer = answer_text
        else:
            db.add(LabAnswer(lab_id=lab.id, task_id=task_id, student_id=user.id, answer=answer_text))
    db.commit()
    return {"lab_id": lab.id, "questions": lab_payload(db, lab, user.id)["questions"], "message": "Answers saved."}


@router.post("/student/labs/{lab_id}/submit", status_code=status.HTTP_201_CREATED)
def submit_lab(lab_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    lab = db.get(Lab, lab_id)
    if lab is None or lab.status != LabStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published lab not found.")
    require_student_access(db, user, lab)
    if not lab.tasks:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This lab has no questions to submit.")
    answers = {
        answer.task_id: answer.answer
        for answer in db.query(LabAnswer).filter(LabAnswer.lab_id == lab.id, LabAnswer.student_id == user.id).all()
    }
    results = []
    auto_score = 0
    for task in lab.tasks:
        answer = answers.get(task.id, "")
        correct, awarded = grade_answer(task, answer)
        auto_score += awarded
        results.append({
            "task_id": task.id,
            "prompt": task.prompt,
            "grading_type": task.grading_type,
            "answer": answer,
            "expected_answer": task.expected_answer or "",
            "correct": correct,
            "points": task.points,
            "awarded_points": awarded,
        })
    submission = LabSubmission(
        lab_id=lab.id,
        student_id=user.id,
        auto_score=auto_score,
        max_score=sum(task.points for task in lab.tasks),
        results=results,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return {**submission_payload(submission), "message": "Lab submitted for teacher review."}


@router.patch("/student/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, payload: ScenarioRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.student_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    if any(session.status == SessionStatus.running for session in scenario.sessions):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stop the scenario before changing its machines.")
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
    if any(session.status == SessionStatus.running for session in scenario.sessions):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stop the scenario before removing it.")
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
        "labs": [lab_payload(db, lab, user.id, include_grading=True) for lab in labs],
        "machines": [machine_payload(machine) for machine in db.query(Machine).filter(Machine.approved.is_(True)).order_by(Machine.name).all()],
        "students": [student_progress_payload(db, student) for student in students],
        "groups": [group_payload(group) for group in managed_groups(db, user)],
        "metrics": {"students": len(students), "labs": len(labs), "running_sessions": running_sessions.count()},
        "reviews": [
            submission_payload(submission, include_answers=True)
            for lab in labs
            for submission in lab.submissions
            if submission.status == "awaiting_review"
        ],
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
    return lab_payload(db, lab, include_grading=True)


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
    return lab_payload(db, lab, include_grading=True)


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


@router.post("/teacher/reviews/{submission_id}")
def complete_review(submission_id: str, payload: FinalizeSubmissionRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    submission = db.get(LabSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    require_lab_manager(user, submission.lab)
    if submission.status == "finalized":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This submission has already been finalized.")
    final_score = submission.auto_score if payload.final_score is None else payload.final_score
    if final_score > submission.max_score:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Final score cannot exceed the available points.")
    submission.final_score = final_score
    submission.feedback = payload.feedback.strip() or None
    submission.status = "finalized"
    submission.finalized_at = datetime.now(timezone.utc)
    submission.finalized_by_id = user.id
    db.commit()
    db.refresh(submission)
    return {**submission_payload(submission, include_answers=True), "message": "Submission finalized."}


@router.get("/admin/dashboard")
def admin_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    running_sessions = db.query(LabSession).filter(LabSession.status == SessionStatus.running).all()
    students = db.query(User).filter(User.role == Role.student).count()
    teachers = db.query(User).filter(User.role == Role.teacher).count()
    return {
        "labs": [lab_payload(db, lab, user.id, include_grading=True) for lab in db.query(Lab).all()],
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


@router.post("/admin/machines/import-github", status_code=status.HTTP_201_CREATED)
def import_github_machine(payload: GitHubMachineImportRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    import_id = str(uuid.uuid4())
    destination = IMPORTED_MACHINES_DIR / import_id
    try:
        archive = download_github_archive(payload.repository_url, payload.ref)
        manifest = install_machine_archive(archive, payload.machine_path, destination)
    except MachineImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to download the GitHub machine repository.") from exc
    if db.query(Machine).filter(Machine.name == str(manifest["name"])).first():
        import shutil
        shutil.rmtree(destination, ignore_errors=True)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A machine with this name already exists.")
    allowed_runtime = {
        "hostname", "command", "entrypoint", "working_dir", "run_as", "restart_policy",
        "privileged", "tty", "stdin_open", "ports", "volumes", "environment", "labels",
        "dns", "extra_hosts", "cap_add", "network_aliases", "detection_profile", "memory_limit", "cpu_limit",
    }
    runtime = {key: manifest[key] for key in allowed_runtime if key in manifest}
    attachments = manifest["attachments"]
    machine = Machine(
        id=import_id,
        name=str(manifest["name"]),
        image_url=str(manifest["image"]),
        source_type="local",
        os_type=str(manifest["os_type"]),
        description=str(manifest["description"]),
        attachment=attachments[0] if attachments else None,
        attachments=attachments,
        build_context=str(destination),
        repository_url=payload.repository_url,
        repository_ref=payload.ref,
        repository_path=payload.machine_path,
        detection_rules=manifest["detection_rules"],
        created_by_id=user.id,
        approved=True,
        **runtime,
    )
    db.add(machine)
    db.add(MachineImportVersion(
        machine_id=machine.id,
        source_digest=machine_content_digest(destination),
        repository_url=payload.repository_url,
        repository_ref=payload.ref,
        repository_path=payload.machine_path,
        manifest=manifest,
        imported_by_id=user.id,
    ))
    db.commit()
    db.refresh(machine)
    return machine_payload(machine)


@router.post("/admin/machines/github-folders")
def list_github_machine_folders(payload: GitHubRepositoryRequest, user: User = Depends(require_roles(Role.admin))):
    try:
        archive = download_github_archive(payload.repository_url, payload.ref)
        folders = discover_machine_folders(archive)
    except MachineImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to inspect the GitHub machine repository.") from exc
    return {"repository_url": payload.repository_url, "ref": payload.ref, "machines": folders}


@router.get("/admin/machines/{machine_id}/versions")
def list_machine_versions(machine_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")
    return [
        {
            "id": version.id,
            "version": index,
            "source_digest": version.source_digest,
            "repository_url": version.repository_url,
            "repository_ref": version.repository_ref,
            "repository_path": version.repository_path,
            "imported_at": version.imported_at.isoformat(),
            "imported_by": version.imported_by.name,
        }
        for index, version in enumerate(machine.import_versions, start=1)
    ]


@router.post("/admin/machines/{machine_id}/refresh-github")
def refresh_github_machine(machine_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")
    if not machine.repository_url or not machine.repository_ref or not machine.repository_path or not machine.build_context:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only machines imported from GitHub can be refreshed.")
    staging = IMPORTED_MACHINES_DIR / (machine.id + "-staging-" + str(uuid.uuid4()))
    target: Path | None = None
    backup: Path | None = None
    swapped = False
    try:
        archive = download_github_archive(machine.repository_url, machine.repository_ref)
        manifest = install_machine_archive(archive, machine.repository_path, staging)
        digest = machine_content_digest(staging)
        latest = machine.import_versions[-1] if machine.import_versions else None
        if latest and latest.source_digest == digest:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The configured repository ref has not changed since the latest import.")
        duplicate = db.query(Machine).filter(Machine.name == str(manifest["name"]), Machine.id != machine.id).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The refreshed manifest name belongs to another machine.")
        target = Path(machine.build_context).resolve()
        backup = IMPORTED_MACHINES_DIR / (machine.id + "-backup-" + str(uuid.uuid4()))
        target.rename(backup)
        try:
            staging.rename(target)
            swapped = True
        except Exception:
            backup.rename(target)
            raise
        allowed_runtime = {
            "hostname", "command", "entrypoint", "working_dir", "run_as", "restart_policy",
            "privileged", "tty", "stdin_open", "ports", "volumes", "environment", "labels",
            "dns", "extra_hosts", "cap_add", "network_aliases", "detection_profile", "memory_limit", "cpu_limit",
        }
        machine.name = str(manifest["name"])
        machine.image_url = str(manifest["image"])
        machine.os_type = str(manifest["os_type"])
        machine.description = str(manifest["description"])
        machine.attachments = manifest["attachments"]
        machine.attachment = manifest["attachments"][0] if manifest["attachments"] else None
        machine.detection_rules = manifest["detection_rules"]
        for key in allowed_runtime:
            if key in manifest:
                setattr(machine, key, manifest[key])
        db.add(MachineImportVersion(
            machine_id=machine.id,
            source_digest=digest,
            repository_url=machine.repository_url,
            repository_ref=machine.repository_ref,
            repository_path=machine.repository_path,
            manifest=manifest,
            imported_by_id=user.id,
        ))
        db.commit()
        db.refresh(machine)
        shutil.rmtree(backup, ignore_errors=True)
        return {**machine_payload(machine), "message": machine.name + " refreshed from GitHub."}
    except HTTPException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except MachineImportError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        db.rollback()
        if swapped and target is not None and backup is not None and backup.exists():
            shutil.rmtree(target, ignore_errors=True)
            backup.rename(target)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to refresh the GitHub machine.") from exc


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
