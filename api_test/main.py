import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from api_test.auth import get_current_user, require_roles
from api_test.config import ASSETS_DIR, AUTH_MODE, MAYAJAL_CORS_ORIGIN_REGEX, MAYAJAL_CORS_ORIGINS, MAYAJAL_SESSION_MAX_MINUTES
from api_test.database import Base, SessionLocal, engine, get_db
from api_test.docker_runtime import DockerProcessError, compose_command, instance_id, run_process, stream_process, verify_compose_project, wait_for_wireguard_config
from api_test.detection_packs import bundle_registry
from api_test.models import Lab, LabAssignment, LabSession, LabStatus, LabTask, Machine, Role, Scenario, ScenarioSession, SessionStatus, StudentGroup, SystemSetting, User
from api_test.pdf_report import render_attack_report_pdf
from api_test.runtime_safety import host_capacity, require_host_capacity
from api_test.schemas import AssignmentCreate, LabCreate, LabRead, LabSessionRead, LoginRequest, MachineCreate, MachineRead, UserRead
from api_test.services import require_lab_manager, require_student_access, start_session, stop_session
from api_test.telemetry import build_attack_report, search_session_events
from api_test.frontend_contract import router as frontend_router, user_payload

logger = logging.getLogger("mayajal.docker")

MACHINE_RUNTIME_COLUMNS = {
    "source_type": "VARCHAR(32) DEFAULT 'dockerhub'",
    "attachment": "VARCHAR(500)",
    "attachments": "JSON",
    "build_context": "VARCHAR(500)",
    "repository_url": "VARCHAR(500)",
    "repository_ref": "VARCHAR(200)",
    "repository_path": "VARCHAR(500)",
    "detection_rules": "JSON",
    "hostname": "VARCHAR(160)",
    "command": "VARCHAR(500)",
    "entrypoint": "VARCHAR(500)",
    "working_dir": "VARCHAR(300)",
    "run_as": "VARCHAR(100)",
    "restart_policy": "VARCHAR(32) DEFAULT 'unless-stopped'",
    "privileged": "BOOLEAN DEFAULT 0",
    "tty": "BOOLEAN DEFAULT 1",
    "stdin_open": "BOOLEAN DEFAULT 0",
    "ports": "JSON",
    "volumes": "JSON",
    "environment": "JSON",
    "labels": "JSON",
    "dns": "JSON",
    "extra_hosts": "JSON",
    "cap_add": "JSON",
    "network_aliases": "JSON",
    "detection_profile": "VARCHAR(100)",
    "memory_limit": "VARCHAR(32) DEFAULT '512m'",
    "cpu_limit": "FLOAT DEFAULT 1.0",
}

TASK_GRADING_COLUMNS = {
    "grading_type": "VARCHAR(20) DEFAULT 'manual'",
    "expected_answer": "VARCHAR(500)",
    "points": "INTEGER DEFAULT 1",
}

DEV_PASSWORDS = {
    "student.maya": "Student!2026",
    "teacher.asha": "Teacher!2026",
    "admin.samir": "Admin!2026",
}


def wireguard_config(lab: Lab, user: User, session_id: str) -> str:
    peer_ip = "10.66." + str(abs(hash(user.id + lab.id)) % 200 + 20) + ".2/32"
    return "\n".join([
        "[Interface]",
        "PrivateKey = REPLACE_WITH_STUDENT_PRIVATE_KEY",
        "Address = " + peer_ip,
        "DNS = 10.66.0.1",
        "",
        "[Peer]",
        "PublicKey = MAYAJAL_LAB_GATEWAY_PUBLIC_KEY",
        "AllowedIPs = 10.66.0.0/16",
        "Endpoint = vpn.mayajal.local:51820",
        "PersistentKeepalive = 25",
        "",
        "# Lab: " + lab.name,
        "# Session: " + session_id,
    ]) + "\n"


def read_lab(lab: Lab) -> LabRead:
    return LabRead(
        id=lab.id,
        name=lab.name,
        description=lab.description,
        status=lab.status,
        owner_id=lab.owner_id,
        machine_ids=[machine.id for machine in lab.machines],
        student_ids=[student.id for student in lab.direct_students],
        group_ids=[group.id for group in lab.groups],
        assigned_student_ids=[assignment.student_id for assignment in lab.assignments],
    )


def resolve_lab_students(db: Session, student_ids: list[str]) -> list[User]:
    if not student_ids:
        return []
    students = db.query(User).filter(User.id.in_(student_ids), User.role == Role.student).all()
    if len(students) != len(set(student_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each assignment must target an existing student.")
    return students


def resolve_lab_groups(db: Session, user: User, group_ids: list[str]) -> list[StudentGroup]:
    if not group_ids:
        return []
    query = db.query(StudentGroup).filter(StudentGroup.id.in_(group_ids))
    if user.role == Role.teacher:
        query = query.filter(StudentGroup.owner_id == user.id)
    groups = query.all()
    if len(groups) != len(set(group_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each group assignment must target a group you manage.")
    return groups


def sync_lab_access(db: Session, lab: Lab, assigned_by_id: str) -> None:
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


def migrate_database() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(machines)").all()}
        for name, ddl in MACHINE_RUNTIME_COLUMNS.items():
            if name not in columns:
                connection.exec_driver_sql(f"ALTER TABLE machines ADD COLUMN {name} {ddl}")
        task_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(lab_tasks)").all()}
        for name, ddl in TASK_GRADING_COLUMNS.items():
            if name not in task_columns:
                connection.exec_driver_sql(f"ALTER TABLE lab_tasks ADD COLUMN {name} {ddl}")
        connection.exec_driver_sql("UPDATE machines SET source_type = 'dockerhub' WHERE source_type IS NULL")
        connection.exec_driver_sql("UPDATE machines SET restart_policy = 'unless-stopped' WHERE restart_policy IS NULL")
        connection.exec_driver_sql("UPDATE machines SET privileged = 0 WHERE privileged IS NULL")
        connection.exec_driver_sql("UPDATE machines SET tty = 1 WHERE tty IS NULL")
        connection.exec_driver_sql("UPDATE machines SET stdin_open = 0 WHERE stdin_open IS NULL")
        for table in ("lab_sessions", "scenario_sessions"):
            session_columns = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})").all()}
            if "expires_at" not in session_columns:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN expires_at DATETIME")
            if "cleanup_status" not in session_columns:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN cleanup_status VARCHAR(32) DEFAULT 'active'")
            if table == "lab_sessions" and "detection_bundle_digest" not in session_columns:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN detection_bundle_digest VARCHAR(64)")
        connection.exec_driver_sql("""
            INSERT OR IGNORE INTO lab_students (lab_id, student_id)
            SELECT lab_id, student_id FROM lab_assignments
        """)


def seed_database() -> None:
    db = SessionLocal()
    try:
        user_specs = [
            ("student.maya", "Maya Patel", "maya.patel@example.local", Role.student),
            ("teacher.asha", "Asha Rana", "asha.rana@example.local", Role.teacher),
            ("admin.samir", "Samir Khan", "samir.khan@example.local", Role.admin),
            ("student.lena", "Lena Chen", "lena.chen@example.local", Role.student),
        ]
        for username, name, email, role in user_specs:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(username=username, name=name, email=email, role=role))
        db.commit()

        admin = db.query(User).filter(User.username == "admin.samir").one()
        teacher = db.query(User).filter(User.username == "teacher.asha").one()
        student = db.query(User).filter(User.username == "student.maya").one()
        machine_specs = [
            ("Kali Workstation", "kalilinux/kali-rolling", "Linux", "Attacker workstation with common security tools."),
            ("DVWA", "vulnerables/web-dvwa", "Linux", "Deliberately vulnerable web application target."),
            ("Suricata Sensor", "jasonish/suricata", "Linux", "Network inspection and alerting sensor."),
        ]
        for name, image_url, os_type, description in machine_specs:
            existing_machine = db.query(Machine).filter(Machine.name == name).first()
            if not existing_machine:
                db.add(Machine(
                    name=name,
                    image_url=image_url,
                    source_type="dockerhub",
                    os_type=os_type,
                    description=description,
                    created_by_id=admin.id,
                ))
        db.commit()

        setting_specs = [
            ("registration", "Student self-registration", False),
            ("teacher_publish", "Teacher lab publishing", True),
            ("machine_review", "Machine image approval", True),
        ]
        for setting_id, label, enabled in setting_specs:
            if not db.get(SystemSetting, setting_id):
                db.add(SystemSetting(id=setting_id, label=label, enabled=enabled))
        db.commit()

        if not db.query(Lab).filter(Lab.name == "Web Exploit Basics").first():
            machines = db.query(Machine).filter(Machine.name.in_(["Kali Workstation", "DVWA"])).all()
            lab = Lab(name="Web Exploit Basics", description="Find and validate common web application weaknesses.", status=LabStatus.published, owner_id=teacher.id, machines=machines, direct_students=[student])
            db.add(lab)
            db.flush()
            for index, prompt in enumerate(["Identify the application login surface.", "Find one injectable input and document the evidence.", "Capture the final proof flag from the vulnerable service."]):
                db.add(LabTask(lab_id=lab.id, prompt=prompt, position=index))
            db.add(LabAssignment(lab_id=lab.id, student_id=student.id, assigned_by_id=teacher.id))
            db.commit()

        if not db.query(Scenario).filter(Scenario.name == "Web observer practice", Scenario.student_id == student.id).first():
            scenario_machines = db.query(Machine).filter(Machine.name.in_(["Kali Workstation", "DVWA"])).all()
            db.add(Scenario(name="Web observer practice", student_id=student.id, machines=scenario_machines))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_database()
    seed_database()
    yield


app = FastAPI(title="Mayajal Core API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=MAYAJAL_CORS_ORIGINS,
    allow_origin_regex=MAYAJAL_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "auth_mode": AUTH_MODE, "capacity": host_capacity()}


@app.post("/admin/runtime/cleanup-expired")
async def cleanup_expired_runtime(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    now = datetime.now(timezone.utc)
    expired_labs = db.query(LabSession).filter(LabSession.status == SessionStatus.running, LabSession.expires_at.is_not(None), LabSession.expires_at <= now).all()
    expired_scenarios = db.query(ScenarioSession).filter(ScenarioSession.status == SessionStatus.running, ScenarioSession.expires_at.is_not(None), ScenarioSession.expires_at <= now).all()
    cleaned: list[str] = []
    failed: list[str] = []
    for session in [*expired_labs, *expired_scenarios]:
        runtime = session.lab if isinstance(session, LabSession) else session.scenario
        try:
            command = compose_command(runtime, "stop", instance_id(runtime, session.student_id), session.student_id, session.id)
            await run_process(command, expose_output=False)
            session.status = SessionStatus.stopped
            session.stopped_at = now
            session.cleanup_status = "expired-cleaned"
            cleaned.append(session.id)
        except Exception:
            logger.exception("Expired runtime cleanup failed for session %s", session.id)
            session.cleanup_status = "cleanup-failed"
            failed.append(session.id)
    db.commit()
    return {"cleaned": cleaned, "failed": failed, "checked_at": now.isoformat()}


@app.post("/auth/login")
def dev_login(payload: LoginRequest, db: Session = Depends(get_db)):
    if AUTH_MODE != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Development login is disabled. Sign in through Microsoft Entra ID.")
    if DEV_PASSWORDS.get(payload.username) != payload.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username or password is incorrect.")
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Development user is unavailable.")
    return {"access_token": "dev:" + user.username, "token_type": "bearer", "user": user_payload(user)}


@app.get("/auth/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


@app.get("/students", response_model=list[UserRead])
def list_students(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    return db.query(User).filter(User.role == Role.student).order_by(User.name).all()


@app.get("/machines", response_model=list[MachineRead])
def list_machines(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Machine)
    if user.role == Role.student:
        query = query.filter(Machine.approved.is_(True))
    return query.order_by(Machine.name).all()


@app.post("/machines", response_model=MachineRead, status_code=status.HTTP_201_CREATED)
def create_machine(payload: MachineCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.admin))):
    if db.query(Machine).filter(Machine.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A machine with this name already exists.")
    machine = Machine(**payload.model_dump(), created_by_id=user.id, approved=True)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


@app.get("/labs", response_model=list[LabRead])
def list_labs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == Role.student:
        labs = db.query(Lab).join(LabAssignment).filter(LabAssignment.student_id == user.id, Lab.status == LabStatus.published).all()
    elif user.role == Role.teacher:
        labs = db.query(Lab).filter(Lab.owner_id == user.id).all()
    else:
        labs = db.query(Lab).all()
    return [read_lab(lab) for lab in labs]


@app.post("/labs", response_model=LabRead, status_code=status.HTTP_201_CREATED)
def create_lab(payload: LabCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    machines = db.query(Machine).filter(Machine.id.in_(payload.machine_ids), Machine.approved.is_(True)).all()
    if len(machines) != len(set(payload.machine_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each lab machine must exist and be approved.")
    students = resolve_lab_students(db, payload.student_ids)
    groups = resolve_lab_groups(db, user, payload.group_ids)
    lab = Lab(name=payload.name, description=payload.description, owner_id=user.id, status=LabStatus.published if payload.publish else LabStatus.draft, machines=machines, direct_students=students, groups=groups)
    db.add(lab)
    db.flush()
    sync_lab_access(db, lab, user.id)
    db.commit()
    db.refresh(lab)
    return read_lab(lab)


@app.post("/labs/{lab_id}/assignments", response_model=LabRead)
def assign_students(lab_id: str, payload: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_lab_manager(user, lab)
    students = db.query(User).filter(User.id.in_(payload.student_ids), User.role == Role.student).all()
    if len(students) != len(set(payload.student_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each assignment must target an existing student.")
    lab.direct_students = list({student.id: student for student in [*lab.direct_students, *students]}.values())
    db.flush()
    existing = {assignment.student_id for assignment in lab.assignments}
    for student in students:
        if student.id not in existing:
            db.add(LabAssignment(lab_id=lab.id, student_id=student.id, assigned_by_id=user.id))
    db.commit()
    db.refresh(lab)
    return read_lab(lab)


@app.get("/labs/{lab_id}", response_model=LabRead)
def get_lab(lab_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    if user.role == Role.student:
        require_student_access(db, user, lab)
    elif user.role == Role.teacher:
        require_lab_manager(user, lab)
    return read_lab(lab)


def require_lab_operator(db: Session, user: User, lab: Lab) -> None:
    if user.role == Role.student:
        require_student_access(db, user, lab)
    elif user.role == Role.teacher:
        require_lab_manager(user, lab)


def require_session_operator(user: User, session: LabSession) -> None:
    if user.role == Role.admin:
        return
    if user.role == Role.teacher and session.lab.owner_id == user.id:
        return
    if user.role == Role.student and session.student_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access telemetry for this session.")


def session_owner_for(user: User, lab: Lab) -> User:
    return user


def lab_operation_unavailable(exc: Exception, user: User) -> HTTPException:
    if user.role == Role.admin:
        if isinstance(exc, HTTPException):
            return exc
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=type(exc).__name__ + ": " + str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Lab containers are not available right now. Ask an administrator to review the container service.",
    )


def lab_operation_failed(exc: Exception, user: User) -> HTTPException:
    if user.role == Role.admin:
        detail = str(exc)
        if isinstance(exc, DockerProcessError) and exc.output:
            detail = exc.output + "\n" + detail
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Lab containers did not reach a confirmed running state. Ask an administrator to review the container output.",
    )


def vpn_filename(lab: Lab, user: User) -> str:
    username = user.username or user.email.split("@")[0]
    return lab.name.lower().replace(" ", "-") + "-" + username.replace(".", "-") + ".conf"


def machine_attachment_names(machine: Machine) -> list[str]:
    return machine.attachments or ([machine.attachment] if machine.attachment else [])


def lab_attachment_downloads(lab: Lab) -> list[dict[str, str]]:
    return [
        {
            "machine_id": machine.id,
            "machine_name": machine.name,
            "filename": Path(attachment).name,
            "download_url": f"/labs/{lab.id}/machines/{machine.id}/attachments/{quote(attachment, safe='')}",
        }
        for machine in lab.machines
        for attachment in machine_attachment_names(machine)
    ]


def machine_attachment_path(machine: Machine, attachment: str | None = None) -> Path:
    available = machine_attachment_names(machine)
    selected = attachment or (available[0] if available else None)
    if not selected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This machine does not have an attachment.")
    if selected not in available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine attachment not found.")
    attachment_root = Path(machine.build_context).resolve() if machine.build_context else ASSETS_DIR.resolve()
    attachment_path = (attachment_root / selected).resolve()
    try:
        attachment_path.relative_to(attachment_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine attachment not found.") from exc
    if not attachment_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine attachment not found.")
    return attachment_path


async def run_stop_command(command: list[str], expose_output: bool = False) -> None:
    try:
        await run_process(command, expose_output=expose_output)
    except Exception:
        logger.exception("Docker Compose stop failed for command: %s", " ".join(command))


async def cleanup_lab_project(lab: Lab, project_id: str, user_id: str, session_id: str, expose_output: bool = False) -> str:
    command = compose_command(lab, "stop", project_id, user_id, session_id)
    try:
        return await run_process(command, expose_output=expose_output)
    except Exception:
        logger.exception("Docker Compose cleanup failed for command: %s", " ".join(command))
        return ""


def require_owned_scenario(db: Session, scenario_id: str, user: User) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.student_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personal scenario not found.")
    if not scenario.machines:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Add at least one approved machine before starting this scenario.")
    if any(not machine.approved for machine in scenario.machines):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This scenario contains a machine that is no longer approved.")
    return scenario


def stop_scenario_session(db: Session, session: ScenarioSession) -> ScenarioSession:
    session.status = SessionStatus.stopped
    session.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


@app.post("/student/scenarios/{scenario_id}/start", status_code=status.HTTP_201_CREATED)
async def start_personal_scenario(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    require_host_capacity()
    scenario = require_owned_scenario(db, scenario_id, user)
    project_id = instance_id(scenario, user.id)
    existing = next((session for session in scenario.sessions if session.status == SessionStatus.running), None)
    if existing is not None:
        try:
            await verify_compose_project(scenario, project_id, timeout_seconds=2)
            config = await wait_for_wireguard_config(project_id, timeout_seconds=5)
            return {"id": existing.id, "scenario_id": scenario.id, "status": "running", "wireguard_config": config, "wireguard_filename": vpn_filename(scenario, user), "message": scenario.name + " is already running."}
        except Exception:
            stop_scenario_session(db, existing)

    session = ScenarioSession(id=str(uuid.uuid4()), scenario_id=scenario.id, student_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(minutes=MAYAJAL_SESSION_MAX_MINUTES))
    try:
        await cleanup_lab_project(scenario, project_id, user.id, session.id)
        command = compose_command(scenario, "start", project_id, user.id, session.id)
        await run_process(command, expose_output=False)
        await verify_compose_project(scenario, project_id)
        config = await wait_for_wireguard_config(project_id)
    except Exception as exc:
        await cleanup_lab_project(scenario, project_id, user.id, session.id)
        raise lab_operation_failed(exc, user) from exc
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "scenario_id": scenario.id, "status": "running", "wireguard_config": config, "wireguard_filename": vpn_filename(scenario, user), "message": scenario.name + " is running and its VPN config is ready."}


@app.get("/student/scenarios/{scenario_id}/vpn")
async def get_personal_scenario_vpn(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    scenario = require_owned_scenario(db, scenario_id, user)
    session = next((item for item in scenario.sessions if item.status == SessionStatus.running), None)
    if session is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start the scenario before downloading its VPN config.")
    project_id = instance_id(scenario, user.id)
    try:
        await verify_compose_project(scenario, project_id, timeout_seconds=2)
        config = await wait_for_wireguard_config(project_id, timeout_seconds=5)
    except Exception as exc:
        stop_scenario_session(db, session)
        raise lab_operation_failed(exc, user) from exc
    return {"scenario_id": scenario.id, "wireguard_config": config, "wireguard_filename": vpn_filename(scenario, user)}


@app.post("/student/scenarios/{scenario_id}/stop")
async def stop_personal_scenario(scenario_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    scenario = require_owned_scenario(db, scenario_id, user)
    session = next((item for item in scenario.sessions if item.status == SessionStatus.running), None)
    if session is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This scenario is not running.")
    project_id = instance_id(scenario, user.id)
    try:
        command = compose_command(scenario, "stop", project_id, user.id, session.id)
    except Exception as exc:
        raise lab_operation_unavailable(exc, user) from exc
    stop_scenario_session(db, session)
    background_tasks.add_task(run_stop_command, command, False)
    return {"id": session.id, "scenario_id": scenario.id, "status": "stopped", "stopped_at": session.stopped_at, "message": scenario.name + " has been stopped."}


@app.post("/labs/{lab_id}/start", status_code=status.HTTP_201_CREATED)
async def start_lab(lab_id: str, stream: bool = Query(False), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_host_capacity()
    lab = db.get(Lab, lab_id)
    if lab is None or lab.status != LabStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published lab not found.")
    require_lab_operator(db, user, lab)
    session_user = session_owner_for(user, lab)
    project_id = instance_id(lab, session_user.id)
    existing_session = next((item for item in lab.sessions if item.student_id == session_user.id and item.status.value == "running"), None)
    if existing_session is not None:
        try:
            await verify_compose_project(lab, project_id, timeout_seconds=2)
        except Exception:
            stop_session(db, existing_session)
            existing_session = None
    planned_session_id = existing_session.id if existing_session is not None else str(uuid.uuid4())
    command = None
    if existing_session is None:
        try:
            await cleanup_lab_project(lab, project_id, session_user.id, planned_session_id, expose_output=False)
            command = compose_command(lab, "start", project_id, session_user.id, planned_session_id)
        except Exception as exc:
            raise lab_operation_unavailable(exc, user) from exc

    if stream:
        if user.role != Role.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can stream lab startup output.")

        async def start_stream():
            if existing_session is not None:
                yield "Lab session is already marked running.\n"
                return
            try:
                if command is None:
                    raise RuntimeError("Docker Compose start command was not prepared.")
                async for chunk in stream_process(command):
                    yield chunk
                yield "\nVerifying Compose project state...\n"
                verification_output = await verify_compose_project(lab, project_id)
                yield verification_output + "\n"
                yield "\nWaiting for WireGuard peer configuration...\n"
                await wait_for_wireguard_config(project_id)
                start_session(db, lab, session_user, planned_session_id)
                yield "Lab containers are confirmed running.\n"
            except Exception as exc:
                await cleanup_lab_project(lab, project_id, session_user.id, planned_session_id, expose_output=False)
                yield "Error: " + str(exc) + "\n"

        return StreamingResponse(start_stream(), media_type="text/plain")

    if existing_session is None:
        try:
            if command is None:
                raise RuntimeError("Docker Compose start command was not prepared.")
            output = await run_process(command, expose_output=user.role == Role.admin)
            verification_output = await verify_compose_project(lab, project_id)
            config = await wait_for_wireguard_config(project_id)
        except Exception as exc:
            await cleanup_lab_project(lab, project_id, session_user.id, planned_session_id, expose_output=False)
            raise lab_operation_failed(exc, user) from exc
        session = start_session(db, lab, session_user, planned_session_id)
    else:
        output = ""
        try:
            config = await wait_for_wireguard_config(project_id)
        except Exception as exc:
            raise lab_operation_failed(exc, user) from exc
        session = existing_session
    response = {
        "id": session.id,
        "lab_id": lab.id,
        "student_id": session_user.id,
        "status": session.status.value,
        "wireguard_config": config,
        "wireguard_filename": vpn_filename(lab, session_user),
        "started_at": session.started_at,
        "stopped_at": session.stopped_at,
        "message": lab.name + " VPN config is ready.",
        "attachments": lab_attachment_downloads(lab),
    }
    if user.role == Role.admin:
        response["output"] = output + ("\n" + verification_output if existing_session is None else "")
    return response


@app.get("/labs/{lab_id}/vpn")
async def get_lab_vpn(lab_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_lab_operator(db, user, lab)
    session_user = session_owner_for(user, lab)
    project_id = instance_id(lab, session_user.id)
    session = next((item for item in lab.sessions if item.student_id == session_user.id and item.status.value == "running"), None)
    if session is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start the lab before downloading the VPN config.")
    try:
        await verify_compose_project(lab, project_id, timeout_seconds=2)
        config = await wait_for_wireguard_config(project_id, timeout_seconds=5)
    except Exception as exc:
        stop_session(db, session)
        raise lab_operation_failed(exc, user) from exc
    return {
        "lab_id": lab.id,
        "wireguard_config": config,
        "wireguard_filename": vpn_filename(lab, session_user),
    }


@app.get("/labs/{lab_id}/machines/{machine_id}/attachment")
def download_machine_attachment(lab_id: str, machine_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _download_machine_attachment(lab_id, machine_id, None, db, user)


@app.get("/labs/{lab_id}/attachments")
def list_lab_attachments(lab_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_lab_operator(db, user, lab)
    session_user = session_owner_for(user, lab)
    running_session = next(
        (item for item in lab.sessions if item.student_id == session_user.id and item.status == SessionStatus.running),
        None,
    )
    if running_session is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start the lab before viewing machine attachments.")
    return {"lab_id": lab.id, "attachments": lab_attachment_downloads(lab)}


@app.get("/labs/{lab_id}/machines/{machine_id}/attachments/{attachment:path}")
def download_named_machine_attachment(attachment: str, lab_id: str, machine_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _download_machine_attachment(lab_id, machine_id, attachment, db, user)


def _download_machine_attachment(lab_id: str, machine_id: str, attachment: str | None, db: Session, user: User):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_lab_operator(db, user, lab)
    machine = next((item for item in lab.machines if item.id == machine_id), None)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found in this lab.")
    session_user = session_owner_for(user, lab)
    running_session = next(
        (item for item in lab.sessions if item.student_id == session_user.id and item.status == SessionStatus.running),
        None,
    )
    if running_session is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start the lab before downloading machine attachments.")
    attachment_path = machine_attachment_path(machine, attachment)
    return FileResponse(attachment_path, filename=attachment_path.name, media_type="text/plain")


@app.post("/labs/{lab_id}/stop", response_model=LabSessionRead)
async def stop_lab(lab_id: str, background_tasks: BackgroundTasks, stream: bool = Query(False), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_lab_operator(db, user, lab)
    session_user = session_owner_for(user, lab)
    project_id = instance_id(lab, session_user.id)
    session = next((item for item in lab.sessions if item.student_id == session_user.id and item.status.value == "running"), None)
    if session is None:
        stopped_session = (
            db.query(LabSession)
            .filter(
                LabSession.lab_id == lab.id,
                LabSession.student_id == session_user.id,
                LabSession.status == SessionStatus.stopped,
            )
            .order_by(LabSession.stopped_at.desc(), LabSession.started_at.desc())
            .first()
        )
        if stopped_session is not None:
            return stopped_session
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You do not have a running session for this lab.")
    try:
        command = compose_command(lab, "stop", project_id, session_user.id, session.id)
    except Exception as exc:
        raise lab_operation_unavailable(exc, user) from exc
    if stream:
        if user.role != Role.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can stream lab shutdown output.")

        async def stop_stream():
            try:
                async for chunk in stream_process(command):
                    yield chunk
                stop_session(db, session)
                yield "Lab session marked stopped.\n"
            except Exception as exc:
                yield "Error: " + str(exc) + "\n"

        return StreamingResponse(stop_stream(), media_type="text/plain")
    stopped_session = stop_session(db, session)
    background_tasks.add_task(run_stop_command, command, user.role == Role.admin)
    return stopped_session


@app.get("/labs/{lab_id}/sessions", response_model=list[LabSessionRead])
def list_sessions(lab_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    if user.role == Role.student:
        require_student_access(db, user, lab)
        return [session for session in lab.sessions if session.student_id == user.id]
    if user.role == Role.teacher:
        require_lab_manager(user, lab)
    return lab.sessions


@app.get("/sessions/{session_id}/telemetry")
def get_session_telemetry(session_id: str, size: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.get(LabSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    require_session_operator(user, session)
    return {"session_id": session_id, "events": search_session_events(session_id, size=size)}


@app.get("/sessions/{session_id}/attack-report")
def get_session_attack_report(session_id: str, size: int = Query(500, ge=1, le=2000), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.get(LabSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    require_session_operator(user, session)
    events = search_session_events(session_id, size=size)
    log_rules = [
        rule
        for machine in session.lab.machines
        for rule in (machine.detection_rules or {}).get("logs", [])
    ]
    registry = bundle_registry(session.detection_bundle_digest) if session.detection_bundle_digest else None
    return build_attack_report(session_id, events, log_rules=log_rules, detection_registry=registry)


@app.get("/sessions/{session_id}/attack-report.pdf")
def download_session_attack_report(session_id: str, size: int = Query(500, ge=1, le=2000), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.get(LabSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    require_session_operator(user, session)
    events = search_session_events(session_id, size=size)
    log_rules = [
        rule
        for machine in session.lab.machines
        for rule in (machine.detection_rules or {}).get("logs", [])
    ]
    registry = bundle_registry(session.detection_bundle_digest) if session.detection_bundle_digest else None
    report = build_attack_report(session_id, events, log_rules=log_rules, detection_registry=registry)
    document = render_attack_report_pdf(report, {
        "lab_name": session.lab.name,
        "student_name": session.student.name,
        "started_at": session.started_at.isoformat(),
        "stopped_at": session.stopped_at.isoformat() if session.stopped_at else None,
    })
    safe_lab_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", session.lab.name).strip("-").lower() or "lab"
    filename = f"mayajal-{safe_lab_name}-{session.id[:8]}-attack-report.pdf"
    return Response(
        content=document,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app.include_router(frontend_router)
