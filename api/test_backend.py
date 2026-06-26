"""Static API fixture for developing the Mayajal frontend without lab infrastructure."""

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Mayajal test API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://192\.168\.\d+\.\d+:3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class ScenarioRequest(BaseModel):
    name: str
    machine_ids: list[str]


USERS = {
    "student.maya": {
        "password": "Student!2026",
        "id": "student-maya",
        "name": "Maya Patel",
        "role": "student",
        "initials": "MP",
    },
    "teacher.asha": {
        "password": "Teacher!2026",
        "id": "teacher-asha",
        "name": "Asha Rana",
        "role": "teacher",
        "initials": "AR",
    },
    "admin.samir": {
        "password": "Admin!2026",
        "id": "admin-samir",
        "name": "Samir Khan",
        "role": "admin",
        "initials": "SK",
    },
}

MACHINES = [
    {
        "id": "machine-kali",
        "name": "Kali Workstation",
        "os_type": "Linux",
        "imageUrl": "kalilinux/kali-rolling",
        "description": "Attacker workstation with common security tools.",
        "added_by": "Admin",
    },
    {
        "id": "machine-dvwa",
        "name": "DVWA",
        "os_type": "Linux",
        "imageUrl": "vulnerables/web-dvwa",
        "description": "Deliberately vulnerable web application target.",
        "added_by": "Teacher",
    },
    {
        "id": "machine-suricata",
        "name": "Suricata Sensor",
        "os_type": "Linux",
        "imageUrl": "jasonish/suricata",
        "description": "Network inspection and alerting sensor.",
        "added_by": "Admin",
    },
    {
        "id": "machine-windows",
        "name": "WinServer 2019",
        "os_type": "Windows",
        "imageUrl": "lab/windows-server-2019",
        "description": "Windows domain and privilege escalation target.",
        "added_by": "Teacher",
    },
]

LABS = [
    {
        "id": "lab-web-exploit",
        "name": "Web Exploit Basics",
        "description": "Find and validate common web application weaknesses.",
        "status": "ready",
        "owner": "Asha Rana",
        "level": "Beginner",
        "runtime": "45 min",
        "progress": 72,
        "next_step": "Complete the input validation module",
        "machine_ids": ["machine-kali", "machine-dvwa"],
    },
    {
        "id": "lab-packet-hunt",
        "name": "Blue Team Packet Hunt",
        "description": "Investigate suspicious traffic and identify indicators.",
        "status": "running",
        "owner": "Security Admin",
        "level": "Intermediate",
        "runtime": "60 min",
        "progress": 35,
        "next_step": "Review the HTTP alert stream",
        "machine_ids": ["machine-kali", "machine-suricata"],
    },
    {
        "id": "lab-windows-path",
        "name": "Windows Privilege Path",
        "description": "Map a privilege escalation path in a Windows environment.",
        "status": "locked",
        "owner": "Asha Rana",
        "level": "Intermediate",
        "runtime": "90 min",
        "progress": 0,
        "next_step": "Unlocks after Packet Hunt",
        "machine_ids": ["machine-kali", "machine-windows"],
    },
]

SCENARIOS = [
    {
        "id": "scenario-web-observer",
        "name": "Web observer practice",
        "status": "saved",
        "machine_ids": ["machine-kali", "machine-dvwa", "machine-suricata"],
        "updated_at": "Today, 10:24",
    },
    {
        "id": "scenario-windows-basics",
        "name": "Windows access path",
        "status": "saved",
        "machine_ids": ["machine-kali", "machine-windows"],
        "updated_at": "Yesterday, 15:40",
    },
]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login")
def login(payload: LoginRequest):
    user = USERS.get(payload.username)
    if user is None or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Username or password is incorrect.")
    return {"access_token": "test-access-token", "token_type": "bearer", "user": {key: value for key, value in user.items() if key != "password"}}


@app.get("/me/")
def get_current_user():
    return {key: value for key, value in USERS["student.maya"].items() if key != "password"}


@app.get("/machines/")
def get_machines():
    return MACHINES


@app.get("/machines/{machine_id}")
def get_machine(machine_id: str):
    machine = next((item for item in MACHINES if item["id"] == machine_id), None)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    return machine


@app.get("/labs/")
def get_labs():
    return LABS


@app.get("/labs/{lab_id}")
def get_lab(lab_id: str):
    lab = next((item for item in LABS if item["id"] == lab_id), None)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@app.api_route("/labs/{lab_id}/start", methods=["GET", "POST"])
def start_lab(lab_id: str):
    lab = next((item for item in LABS if item["id"] == lab_id), None)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    if lab["status"] == "locked":
        raise HTTPException(status_code=403, detail="Complete the prerequisite lab before starting this one.")
    return {
        "lab_id": lab_id,
        "status": "running",
        "message": lab["name"] + " is ready.",
        "access_url": "https://lab.mayajal.local/session/" + lab_id,
    }


@app.get("/student/dashboard")
def student_dashboard():
    return {
        "student": {key: value for key, value in USERS["student.maya"].items() if key != "password"},
        "assignments": LABS,
        "machines": MACHINES,
        "scenarios": SCENARIOS,
        "activity": [
            {"id": "activity-1", "title": "Resumed Blue Team Packet Hunt", "detail": "25 minutes of lab time", "when": "Today, 11:40"},
            {"id": "activity-2", "title": "Saved Web observer practice", "detail": "3 machines selected", "when": "Today, 10:24"},
            {"id": "activity-3", "title": "Completed reflected XSS module", "detail": "Web Exploit Basics", "when": "Yesterday, 16:05"},
        ],
    }


@app.post("/student/scenarios", status_code=201)
def save_scenario(payload: ScenarioRequest):
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="A scenario name is required.")
    if not payload.machine_ids:
        raise HTTPException(status_code=422, detail="Select at least one approved machine.")
    return {
        "id": "scenario-new",
        "name": payload.name.strip(),
        "status": "saved",
        "machine_ids": payload.machine_ids,
        "updated_at": "Just now",
    }


class TeacherLabRequest(BaseModel):
    name: str


class MachineRequest(BaseModel):
    name: str
    os_type: str


class RoleRequest(BaseModel):
    role: Literal["student", "teacher", "admin"]


class SettingRequest(BaseModel):
    enabled: bool


TEACHER_STUDENTS = [
    {"id": "student-maya", "name": "Maya Patel", "cohort": "Security Foundations", "active_labs": 2, "progress": 54},
    {"id": "student-lena", "name": "Lena Chen", "cohort": "Security Foundations", "active_labs": 1, "progress": 81},
    {"id": "student-noah", "name": "Noah Williams", "cohort": "Incident Response", "active_labs": 2, "progress": 63},
]

REVIEWS = [
    {"id": "review-1", "student": "Amir Hussain", "lab": "Windows Privilege Path", "state": "Ready for review"},
    {"id": "review-2", "student": "Lena Chen", "lab": "Web Exploit Basics", "state": "Requested help"},
    {"id": "review-3", "student": "Noah Williams", "lab": "Blue Team Packet Hunt", "state": "Completed"},
]

ADMIN_USERS = [
    {"id": "student-maya", "name": "Maya Patel", "username": "student.maya", "role": "student", "status": "Active"},
    {"id": "teacher-asha", "name": "Asha Rana", "username": "teacher.asha", "role": "teacher", "status": "Active"},
    {"id": "admin-samir", "name": "Samir Khan", "username": "admin.samir", "role": "admin", "status": "Active"},
    {"id": "student-lena", "name": "Lena Chen", "username": "student.lena", "role": "student", "status": "Active"},
]

SETTINGS = [
    {"id": "registration", "label": "Student self-registration", "enabled": False},
    {"id": "teacher_publish", "label": "Teacher lab publishing", "enabled": True},
    {"id": "machine_review", "label": "Machine image approval", "enabled": True},
]


@app.get("/teacher/dashboard")
def teacher_dashboard():
    return {"labs": LABS, "machines": MACHINES, "students": TEACHER_STUDENTS, "reviews": REVIEWS}


@app.post("/teacher/labs", status_code=201)
def create_teacher_lab(payload: TeacherLabRequest):
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="A lab name is required.")
    return {
        "id": "lab-new",
        "name": payload.name.strip(),
        "description": "New classroom lab ready for configuration.",
        "status": "ready",
        "owner": "Asha Rana",
        "level": "Beginner",
        "runtime": "45 min",
        "progress": 0,
        "next_step": "Select machines and publish to a class",
        "machine_ids": ["machine-kali", "machine-dvwa"],
    }


@app.post("/teacher/reviews/{review_id}")
def complete_review(review_id: str):
    review = next((item for item in REVIEWS if item["id"] == review_id), None)
    if review is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    return {"id": review_id, "message": "Feedback recorded for " + review["student"] + "."}


@app.get("/admin/dashboard")
def admin_dashboard():
    return {
        "labs": LABS,
        "machines": MACHINES,
        "users": ADMIN_USERS,
        "settings": SETTINGS,
        "health": [
            {"name": "Lab scheduler", "value": "Healthy"},
            {"name": "Machine catalogue", "value": "42 images"},
            {"name": "Access policies", "value": "Enforced"},
        ],
    }


@app.post("/admin/machines", status_code=201)
def create_admin_machine(payload: MachineRequest):
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="A machine name is required.")
    return {
        "id": "machine-new",
        "name": payload.name.strip(),
        "os_type": payload.os_type,
        "imageUrl": "registry.mayajal.local/" + payload.name.lower().replace(" ", "-"),
        "description": "Approved machine image ready for lab use.",
        "added_by": "Admin",
    }


@app.patch("/admin/users/{user_id}/role")
def change_role(user_id: str, payload: RoleRequest):
    user = next((item for item in ADMIN_USERS if item["id"] == user_id), None)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user_id, "role": payload.role, "message": user["name"] + " now has " + payload.role + " access."}


@app.patch("/admin/settings/{setting_id}")
def change_setting(setting_id: str, payload: SettingRequest):
    setting = next((item for item in SETTINGS if item["id"] == setting_id), None)
    if setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"id": setting_id, "enabled": payload.enabled, "message": setting["label"] + " updated."}
