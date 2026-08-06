# Mayajal Core API

This service contains the role-aware core backend. It is separate from the temporary fixture API and uses SQLite for local development.

## Run locally

From the repository root:

    uv run --project api_test uvicorn api_test.main:app --host 0.0.0.0 --port 8001

API docs are available at http://127.0.0.1:8001/docs.

## Telemetry stack

Start the central OpenSearch, OpenSearch Dashboards, and Fluent Bit receiver before running labs:

    docker compose -f assets/telemetry_compose.yml up -d

OpenSearch listens on http://127.0.0.1:9200. OpenSearch Dashboards listens on http://127.0.0.1:5601. Lab sessions forward Suricata `eve.json` events and container stdout with `session_id`, `lab_id`, `user_id`, and `project_id` metadata. Query `mayajal-logs-*` in Dashboards or use the API session telemetry endpoints.

Useful environment overrides:

    MAYAJAL_OPENSEARCH_URL=http://127.0.0.1:9200
    MAYAJAL_OPENSEARCH_INDEX=mayajal-logs-*
    MAYAJAL_TELEMETRY_HOST=host.docker.internal
    MAYAJAL_TELEMETRY_PORT=24224

## Development accounts

- student.maya / Student!2026
- teacher.asha / Teacher!2026
- admin.samir / Admin!2026

Development login returns a local bearer token. It is available only while AUTH_MODE=dev.

## Microsoft Entra ID

Set AUTH_MODE=entra and configure ENTRA_TENANT_ID and ENTRA_CLIENT_ID. ENTRA_AUDIENCE is optional and defaults to ENTRA_CLIENT_ID.

The service validates bearer tokens against the Microsoft Entra OpenID Connect signing keys. Entra app roles are authoritative on every request. Configure app roles named student, teacher, and admin (or mayajal.admin and mayajal.teacher). Students are restricted to assigned published labs; teachers and administrators can create machines and labs; administrators retain platform-wide access.

## Core routes

- POST /auth/login and GET /auth/me
- GET/POST /machines
- GET /students
- GET/POST /labs and POST /labs/{lab_id}/assignments
- POST /labs/{lab_id}/start and POST /labs/{lab_id}/stop
- GET /labs/{lab_id}/sessions
- GET /sessions/{session_id}/telemetry
- GET /sessions/{session_id}/attack-report

## Importing vulnerable machines from GitHub

An administrator can import one machine folder from a public GitHub repository:

    POST /admin/machines/import-github
    {
      "repository_url": "https://github.com/monkey-with-a-flower/mayajal-vulnerable-machines",
      "ref": "main",
      "machine_path": "weak-password-login"
    }

Every machine folder must contain `machine.json` and `Dockerfile`. Put optional
learner downloads beneath `attachments/`. The manifest requires `name`, `image`,
`os_type`, `description`, and at least one detection declaration; it can also
contain supported runtime fields such as `ports`, `environment`,
`network_aliases`, and `restart_policy`.
Imported files become that machine's Docker build context. Attachment download
URLs are returned when the lab starts and remain authorized only while that
user's lab session is running.

Detection layout:

    detections/network/*.rules          # Suricata, loaded at lab startup
    detections/application-logs/*.json  # container/application log matcher
    detections/system-logs/*.json       # syslog/journald/audit matcher

`machine.json` selects files through `detection.network.suricata`,
`detection.logs.application`, and `detection.logs.system`. Log rules contain an
event field and regular expression plus their ATT&CK tactic and technique. They
are applied to session telemetry before the attack chain is generated.
