from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from api_test.auth import get_current_user, require_roles
from api_test.config import AUTH_MODE
from api_test.database import Base, SessionLocal, engine, get_db
from api_test.models import Lab, LabAssignment, LabStatus, LabTask, Machine, Role, Scenario, SystemSetting, User
from api_test.schemas import AssignmentCreate, LabCreate, LabRead, LabSessionRead, LoginRequest, MachineCreate, MachineRead, UserRead
from api_test.services import require_lab_manager, require_student_access, start_session, stop_session
from api_test.frontend_contract import router as frontend_router, user_payload

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
        student_ids=[assignment.student_id for assignment in lab.assignments],
    )


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
            if not db.query(Machine).filter(Machine.name == name).first():
                db.add(Machine(name=name, image_url=image_url, os_type=os_type, description=description, created_by_id=admin.id))
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
            lab = Lab(name="Web Exploit Basics", description="Find and validate common web application weaknesses.", status=LabStatus.published, owner_id=teacher.id, machines=machines)
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
    seed_database()
    yield


app = FastAPI(title="Mayajal Core API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "auth_mode": AUTH_MODE}


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
def create_machine(payload: MachineCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.teacher, Role.admin))):
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
    students = []
    if payload.student_ids:
        students = db.query(User).filter(User.id.in_(payload.student_ids), User.role == Role.student).all()
        if len(students) != len(set(payload.student_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each assignment must target an existing student.")
    lab = Lab(name=payload.name, description=payload.description, owner_id=user.id, status=LabStatus.published if payload.publish else LabStatus.draft, machines=machines)
    db.add(lab)
    db.flush()
    for student in students:
        db.add(LabAssignment(lab_id=lab.id, student_id=student.id, assigned_by_id=user.id))
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


@app.post("/labs/{lab_id}/start", status_code=status.HTTP_201_CREATED)
def start_lab(lab_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    lab = db.get(Lab, lab_id)
    if lab is None or lab.status != LabStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published lab not found.")
    require_student_access(db, user, lab)
    session = start_session(db, lab, user)
    filename = lab.name.lower().replace(" ", "-") + "-" + user.username.replace(".", "-") + ".conf"
    return {
        "id": session.id,
        "lab_id": lab.id,
        "student_id": user.id,
        "status": session.status.value,
        "wireguard_config": wireguard_config(lab, user, session.id),
        "wireguard_filename": filename,
        "started_at": session.started_at,
        "stopped_at": session.stopped_at,
        "message": lab.name + " VPN config is ready.",
    }


@app.post("/labs/{lab_id}/stop", response_model=LabSessionRead)
def stop_lab(lab_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab not found.")
    require_student_access(db, user, lab)
    session = next((item for item in lab.sessions if item.student_id == user.id and item.status.value == "running"), None)
    if session is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You do not have a running session for this lab.")
    return stop_session(db, session)


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


app.include_router(frontend_router)
