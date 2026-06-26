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
