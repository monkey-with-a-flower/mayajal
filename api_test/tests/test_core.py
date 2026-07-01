import os
from pathlib import Path

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

TEST_DB = Path(__file__).parent / "test_mayajal.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "dev"

from api_test.database import Base, SessionLocal, engine
from api_test.docker_runtime import prepare_lab_runtime
from api_test.main import app
from api_test.models import Lab


@pytest.fixture(scope="module", autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture()
def client(monkeypatch):
    async def fake_run_process(command: list[str], expose_output: bool = False) -> str:
        return (" ".join(command) + "\nProcess exited with code 0\n") if expose_output else ""

    async def fake_verify_compose_project(lab, project_id: str, timeout_seconds: int = 45) -> str:
        return '[{"Service":"wireguard","State":"running"}]\n'

    async def fake_wait_for_wireguard_config(project_id: str, timeout_seconds: int = 60) -> str:
        return "[Interface]\nPrivateKey = TEST\n"

    monkeypatch.setattr("api_test.main.compose_command", lambda lab, action, project_id, peer_id, session_id: ["docker", "compose", action, project_id, session_id])
    monkeypatch.setattr("api_test.main.run_process", fake_run_process)
    monkeypatch.setattr("api_test.main.verify_compose_project", fake_verify_compose_project)
    monkeypatch.setattr("api_test.main.wait_for_wireguard_config", fake_wait_for_wireguard_config)
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
    assert "output" not in started.json()
    assert "[Interface]" in started.json()["wireguard_config"]
    assert started.json()["wireguard_filename"].endswith(".conf")
    vpn = client.get(f"/labs/{lab_id}/vpn", headers=headers)
    assert vpn.status_code == 200
    assert "[Interface]" in vpn.json()["wireguard_config"]
    stopped = client.post(f"/labs/{lab_id}/stop", headers=headers)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    stopped_again = client.post(f"/labs/{lab_id}/stop", headers=headers)
    assert stopped_again.status_code == 200
    assert stopped_again.json()["status"] == "stopped"


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


def test_lab_running_state_is_scoped_to_current_user_instance(client: TestClient):
    teacher = login(client, "teacher.asha", "Teacher!2026")
    student = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/teacher/dashboard", headers=teacher).json()["labs"][0]["id"]

    started = client.post(f"/labs/{lab_id}/start", headers=teacher)
    assert started.status_code == 201

    teacher_lab = next(lab for lab in client.get("/teacher/dashboard", headers=teacher).json()["labs"] if lab["id"] == lab_id)
    student_lab = next(lab for lab in client.get("/student/dashboard", headers=student).json()["assignments"] if lab["id"] == lab_id)
    assert teacher_lab["status"] == "running"
    assert student_lab["status"] == "ready"

    stopped = client.post(f"/labs/{lab_id}/stop", headers=teacher)
    assert stopped.status_code == 200


def test_stop_returns_clean_state_when_shutdown_command_fails(client: TestClient, monkeypatch):
    headers = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/labs", headers=headers).json()[0]["id"]
    started = client.post(f"/labs/{lab_id}/start", headers=headers)
    assert started.status_code == 201

    async def fail_run_process(command: list[str], expose_output: bool = False) -> str:
        raise RuntimeError("network route closed during compose down")

    monkeypatch.setattr("api_test.main.run_process", fail_run_process)
    stopped = client.post(f"/labs/{lab_id}/stop", headers=headers)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"


def test_session_attack_report_uses_authorized_session_telemetry(client: TestClient, monkeypatch):
    headers = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/labs", headers=headers).json()[0]["id"]
    started = client.post(f"/labs/{lab_id}/start", headers=headers)
    assert started.status_code == 201
    session_id = started.json()["id"]

    monkeypatch.setattr("api_test.main.search_session_events", lambda requested_session_id, size=500: [{
        "session_id": requested_session_id,
        "@timestamp": "2026-07-01T00:00:00Z",
        "event_type": "alert",
        "src_ip": "10.66.1.2",
        "dest_ip": "172.20.1.10",
        "alert": {"signature": "ET SCAN Nmap Scripting Engine User-Agent Detected", "category": "Attempted Information Leak"},
    }])
    report = client.get(f"/sessions/{session_id}/attack-report", headers=headers)
    assert report.status_code == 200
    assert report.json()["session_id"] == session_id
    assert report.json()["attack_chain"][0]["tactic"] == "Reconnaissance"
    assert report.json()["attack_chain"][0]["technique_id"] == "T1595"
    stopped = client.post(f"/labs/{lab_id}/stop", headers=headers)
    assert stopped.status_code == 200


def test_rendered_suricata_config_logs_http_events(client: TestClient):
    headers = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/labs", headers=headers).json()[0]["id"]
    db = SessionLocal()
    try:
        lab = db.get(Lab, lab_id)
        assert lab is not None
        lab_dir = prepare_lab_runtime(lab, "test-http-telemetry", "test-user", "test-session")
        config = (lab_dir / "generated" / "suricata" / "suricata.yaml").read_text()
    finally:
        db.close()
    assert "- http:" in config
    assert "enabled: yes" in config[config.index("- http:"):config.index("# ---- DNS")]


def test_rendered_wireguard_template_preserves_peer_source_ip(client: TestClient):
    headers = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/labs", headers=headers).json()[0]["id"]
    db = SessionLocal()
    try:
        lab = db.get(Lab, lab_id)
        assert lab is not None
        lab_dir = prepare_lab_runtime(lab, "test-routed-wireguard", "test-user", "test-session", refresh_vpn_config=True)
        template = (lab_dir / "config" / "wireguard" / "templates" / "server.conf").read_text()
        env = (lab_dir / ".env").read_text()
    finally:
        db.close()
    assert "MASQUERADE" not in template
    assert "LABGATEWAY=" in env


def test_student_start_failure_hides_docker_output(client: TestClient, monkeypatch):
    async def fail_run_process(command: list[str], expose_output: bool = False) -> str:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lab containers could not complete the requested operation. Ask an administrator to review the container output.",
        )

    monkeypatch.setattr("api_test.main.run_process", fail_run_process)
    headers = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/labs", headers=headers).json()[0]["id"]
    started = client.post(f"/labs/{lab_id}/start", headers=headers)
    assert started.status_code == 500
    assert "docker compose" not in started.json()["detail"].lower()
    assert "Process exited" not in started.json()["detail"]
    dashboard = client.get("/student/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert next(lab for lab in dashboard.json()["assignments"] if lab["id"] == lab_id)["status"] == "ready"


def test_start_verification_failure_does_not_mark_lab_running(client: TestClient, monkeypatch):
    async def fail_verify_compose_project(lab, project_id: str, timeout_seconds: int = 45) -> str:
        raise RuntimeError("compose project did not become healthy")

    monkeypatch.setattr("api_test.main.verify_compose_project", fail_verify_compose_project)
    headers = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/labs", headers=headers).json()[0]["id"]
    started = client.post(f"/labs/{lab_id}/start", headers=headers)
    assert started.status_code == 500
    dashboard = client.get("/student/dashboard", headers=headers)
    assert next(lab for lab in dashboard.json()["assignments"] if lab["id"] == lab_id)["status"] == "ready"


def test_student_start_hides_compose_availability_details(client: TestClient, monkeypatch):
    def fail_compose_command(lab, action, project_id, peer_id, session_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docker Compose is not available on this host.",
        )

    monkeypatch.setattr("api_test.main.compose_command", fail_compose_command)
    headers = login(client, "student.maya", "Student!2026")
    lab_id = client.get("/labs", headers=headers).json()[0]["id"]
    started = client.post(f"/labs/{lab_id}/start", headers=headers)
    assert started.status_code == 503
    assert "docker" not in started.json()["detail"].lower()
    assert "compose" not in started.json()["detail"].lower()


def test_admin_start_setup_failure_shows_exact_error(client: TestClient, monkeypatch):
    def fail_compose_command(lab, action, project_id, peer_id, session_id):
        raise RuntimeError("base compose template is missing LABSUBNET")

    monkeypatch.setattr("api_test.main.compose_command", fail_compose_command)
    headers = login(client, "admin.samir", "Admin!2026")
    lab_id = client.get("/admin/dashboard", headers=headers).json()["labs"][0]["id"]
    started = client.post(f"/labs/{lab_id}/start?stream=true", headers=headers)
    assert started.status_code == 503
    assert "RuntimeError: base compose template is missing LABSUBNET" in started.json()["detail"]


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


def test_student_cannot_edit_another_students_scenario(client: TestClient):
    maya = login(client, "student.maya", "Student!2026")
    lena = {"Authorization": "Bearer dev:student.lena"}
    machine_id = client.get("/student/dashboard", headers=maya).json()["machines"][0]["id"]
    scenario = client.post("/student/scenarios", headers=maya, json={"name": "Maya private scenario", "machine_ids": [machine_id]})
    assert scenario.status_code == 201
    blocked = client.patch(f"/student/scenarios/{scenario.json()['id']}", headers=lena, json={"name": "Lena edit attempt", "machine_ids": [machine_id]})
    assert blocked.status_code == 404


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


def test_teacher_groups_control_dashboard_lab_visibility(client: TestClient):
    teacher = login(client, "teacher.asha", "Teacher!2026")
    lena = {"Authorization": "Bearer dev:student.lena"}
    dashboard = client.get("/teacher/dashboard", headers=teacher).json()
    machine_id = dashboard["machines"][0]["id"]
    lena_id = next(student["id"] for student in dashboard["students"] if student["name"] == "Lena Chen")

    group = client.post("/teacher/groups", headers=teacher, json={"name": "Lena cohort", "student_ids": [lena_id]})
    assert group.status_code == 201
    assert group.json()["student_count"] == 1

    lab = client.post("/teacher/labs", headers=teacher, json={
        "name": "Grouped Teacher Lab",
        "description": "Students in a selected group should receive this investigation.",
        "machine_ids": [machine_id],
        "tasks": ["Confirm the assigned target."],
        "group_ids": [group.json()["id"]],
        "student_ids": [],
        "publish": True,
    })
    assert lab.status_code == 201
    assert lab.json()["assigned_count"] == 1
    assert lab.json()["id"] in {item["id"] for item in client.get("/student/dashboard", headers=lena).json()["assignments"]}

    updated_group = client.patch("/teacher/groups/" + group.json()["id"], headers=teacher, json={"name": "Lena cohort", "student_ids": []})
    assert updated_group.status_code == 200
    assert updated_group.json()["student_count"] == 0
    assert lab.json()["id"] not in {item["id"] for item in client.get("/student/dashboard", headers=lena).json()["assignments"]}


def test_admin_can_create_machine_with_runtime_options(client: TestClient):
    admin = login(client, "admin.samir", "Admin!2026")
    created = client.post("/admin/machines", headers=admin, json={
        "name": "Runtime Rich Target",
        "image_url": "registry.example.local/labs/runtime-rich:1.0",
        "source_type": "custom",
        "os_type": "Linux",
        "description": "Container with explicit runtime settings.",
        "hostname": "rich-target",
        "command": "python app.py",
        "entrypoint": "/bin/sh -c",
        "working_dir": "/opt/app",
        "run_as": "1000:1000",
        "restart_policy": "on-failure",
        "privileged": True,
        "tty": False,
        "stdin_open": True,
        "ports": ["8080:80"],
        "volumes": ["./evidence:/evidence:ro"],
        "environment": {"FLAG": "mayajal{test}"},
        "labels": {"mayajal.role": "target"},
        "dns": ["1.1.1.1"],
        "extra_hosts": ["host.docker.internal:host-gateway"],
        "cap_add": ["NET_ADMIN"],
        "network_aliases": ["target"],
    })
    assert created.status_code == 201
    body = created.json()
    assert body["source_type"] == "custom"
    assert body["ports"] == ["8080:80"]
    assert body["environment"] == {"FLAG": "mayajal{test}"}
    assert body["privileged"] is True


def test_admin_can_update_configured_machine(client: TestClient):
    admin = login(client, "admin.samir", "Admin!2026")
    created = client.post("/admin/machines", headers=admin, json={
        "name": "Editable Machine Target",
        "image_url": "vulnerables/web-dvwa:latest",
        "source_type": "dockerhub",
        "os_type": "Linux",
        "description": "Initial target.",
    })
    assert created.status_code == 201
    updated = client.patch(f"/admin/machines/{created.json()['id']}", headers=admin, json={
        "name": "Edited Machine Target",
        "image_url": "local/edited-target:dev",
        "source_type": "local",
        "os_type": "Linux",
        "description": "Updated target.",
        "hostname": "edited-target",
        "restart_policy": "always",
        "ports": ["8081:80"],
        "volumes": ["./edited:/edited"],
        "environment": {"MODE": "edited"},
    })
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "Edited Machine Target"
    assert body["source_type"] == "local"
    assert body["ports"] == ["8081:80"]
    assert body["environment"] == {"MODE": "edited"}
