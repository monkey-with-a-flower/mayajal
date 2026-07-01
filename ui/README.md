# Mayajal UI

## Local development

Start the API from the repository root:

    uv run --project api_test uvicorn api_test.main:app --host 0.0.0.0 --port 8001

Start the frontend from this directory. Use the machine LAN address when opening it from another device:

    npm run dev -- --hostname 0.0.0.0 --port 3000

The frontend reads MAYAJAL_API_URL or NEXT_PUBLIC_API_URL when it starts. If neither is set, it uses the same hostname as the browser and port 8001, so http://192.168.1.33:3000 will call http://192.168.1.33:8001.

## Fixture accounts

| Role | Username | Password |
| --- | --- | --- |
| Student | student.maya | Student!2026 |
| Teacher | teacher.asha | Teacher!2026 |
| Administrator | admin.samir | Admin!2026 |
