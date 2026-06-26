# Mayajal UI

## Local development

Start the fixture API from the repository root:

    api/.venv/bin/python -m uvicorn api.test_backend:app --host 0.0.0.0 --port 8000

Start the frontend from this directory. Use the machine LAN address when opening it from another device:

    MAYAJAL_API_URL=http://192.168.0.223:8000 npm run dev -- --hostname 0.0.0.0 --port 3000

The frontend reads MAYAJAL_API_URL or NEXT_PUBLIC_API_URL when it starts, so the API endpoint can be configured independently.

## Fixture accounts

| Role | Username | Password |
| --- | --- | --- |
| Student | student.maya | Student!2026 |
| Teacher | teacher.asha | Teacher!2026 |
| Administrator | admin.samir | Admin!2026 |
