# Mayajal Streamlit UI

The dashboard covers the API's user, machine, and lab CRUD operations, streams
lab start/stop output, downloads WireGuard configuration, and runs the local
Suricata correlation report.

From the repository root:

```bash
uv run --project api uvicorn api.main:app --reload
python -m pip install -r ui/requirements.txt
streamlit run ui/main.py
```

The UI defaults to `http://127.0.0.1:8000` and lets you change the API URL in
the sidebar.
