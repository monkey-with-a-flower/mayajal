import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path(__file__).parent / "test_mayajal.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "dev"

from api_test.database import Base, engine
from api_test.main import app


@pytest.fixture(scope="module", autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_student_only_sees_assigned_lab_and_can_manage_own_session(client: TestClient):
    headers = login(client, "student.maya", "Student!2026")
    labs = client.get("/labs", headers=headers)
    assert labs.status_code == 200
    assert len(labs.json()) == 1
    lab_id = labs.json()[0]["id"]
    started = client.post(f"/labs/{lab_id}/start", headers=headers)
    assert started.status_code == 201
    assert started.json()["status"] == "running"
    assert "[Interface]" in started.json()["wireguard_config"]
    assert started.json()["wireguard_filename"].endswith(".conf")
    stopped = client.post(f"/labs/{lab_id}/stop", headers=headers)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"


def test_teacher_assignment_controls_student_access(client: TestClient):
    teacher = login(client, "teacher.asha", "Teacher!2026")
    student = login(client, "student.maya", "Student!2026")
    machines = client.get("/machines", headers=teacher).json()
    students = client.get("/students", headers=teacher).json()
    maya = next(user for user in students if user["username"] == "student.maya")

    assigned = client.post("/labs", headers=teacher, json={
        "name": "Assigned Teacher Lab",
        "machine_ids": [machines[0]["id"]],
        "student_ids": [maya["id"]],
        "publish": True,
    })
    assert assigned.status_code == 201
    assert assigned.json()["id"] in {lab["id"] for lab in client.get("/labs", headers=student).json()}

    private = client.post("/labs", headers=teacher, json={
        "name": "Unassigned Teacher Lab",
        "machine_ids": [machines[0]["id"]],
        "student_ids": [],
        "publish": True,
    })
    assert private.status_code == 201
    assert client.get(f"/labs/{private.json()['id']}", headers=student).status_code == 403
    assert client.post("/labs", headers=student, json={"name": "Denied", "machine_ids": [machines[0]["id"]]}).status_code == 403


def test_frontend_contract_uses_authenticated_core_data(client: TestClient):
    login_response = client.post("/auth/login", json={"username": "student.maya", "password": "Student!2026"})
    assert login_response.status_code == 200
    assert login_response.json()["user"]["initials"] == "MP"
    headers = {"Authorization": "Bearer " + login_response.json()["access_token"]}
    dashboard = client.get("/student/dashboard", headers=headers)
    assert dashboard.status_code == 200
    machine_id = dashboard.json()["machines"][0]["id"]
    scenario = client.post("/student/scenarios", headers=headers, json={"name": "UI contract scenario", "machine_ids": [machine_id]})
    assert scenario.status_code == 201
    assert scenario.json()["name"] == "UI contract scenario"
    updated = client.patch(f"/student/scenarios/{scenario.json()['id']}", headers=headers, json={"name": "Updated UI scenario", "machine_ids": [machine_id]})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated UI scenario"
    deleted = client.delete(f"/student/scenarios/{scenario.json()['id']}", headers=headers)
    assert deleted.status_code == 200


def test_teacher_can_update_and_remove_owned_dashboard_labs(client: TestClient):
    teacher = login(client, "teacher.asha", "Teacher!2026")
    machines = client.get("/machines", headers=teacher).json()
    created = client.post("/teacher/labs", headers=teacher, json={
        "name": "Editable Teacher Lab",
        "description": "A company payroll portal is showing suspicious behavior and needs triage.",
        "machine_ids": [machines[0]["id"]],
        "tasks": ["Find the exposed service.", "Capture the payroll flag."],
        "publish": True,
    })
    assert created.status_code == 201
    lab_id = created.json()["id"]
    assert created.json()["machine_ids"] == [machines[0]["id"]]
    assert created.json()["tasks"] == ["Find the exposed service.", "Capture the payroll flag."]

    updated = client.patch("/teacher/labs/" + lab_id, headers=teacher, json={
        "name": "Edited Teacher Lab",
        "description": "Updated from the teacher dashboard.",
        "machine_ids": [machines[1]["id"]],
        "tasks": ["Document the entry point.", "Submit the admin flag."],
        "publish": False,
    })
    assert updated.status_code == 200
    assert updated.json()["name"] == "Edited Teacher Lab"
    assert updated.json()["description"] == "Updated from the teacher dashboard."
    assert updated.json()["machine_ids"] == [machines[1]["id"]]
    assert updated.json()["tasks"] == ["Document the entry point.", "Submit the admin flag."]
    assert updated.json()["status"] == "locked"

    deleted = client.delete("/teacher/labs/" + lab_id, headers=teacher)
    assert deleted.status_code == 200
    assert lab_id not in {lab["id"] for lab in client.get("/teacher/dashboard", headers=teacher).json()["labs"]}
