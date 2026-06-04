import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_API_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 30

st.set_page_config(page_title="Mayajal Control Plane", page_icon="M", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --mayajal-bg: #071416;
        --mayajal-panel: #102326;
        --mayajal-panel-soft: #162d30;
        --mayajal-border: #284448;
        --mayajal-text: #eff8f6;
        --mayajal-muted: #a6c2be;
        --mayajal-accent: #42c7b9;
        --mayajal-warm: #e5a84b;
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        background:
            radial-gradient(circle at 85% 8%, rgba(31, 124, 117, .22), transparent 28rem),
            radial-gradient(circle at 8% 90%, rgba(188, 126, 43, .10), transparent 25rem),
            var(--mayajal-bg);
        color: var(--mayajal-text);
    }
    [data-testid="stHeader"] { background: rgba(7, 20, 22, .82); }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #102a2e 0%, #091a1c 100%);
        border-right: 1px solid var(--mayajal-border);
    }
    [data-testid="stSidebar"] * { color: var(--mayajal-text); }
    [data-testid="stSidebarNav"] { background: transparent; }
    h1, h2, h3, h4, p, label, .stMarkdown { color: var(--mayajal-text); }
    .stCaption, [data-testid="stCaptionContainer"] { color: var(--mayajal-muted); }
    .hero {
        padding: 1.8rem 2rem;
        border: 1px solid #376b69;
        border-radius: 20px;
        color: white;
        background: linear-gradient(120deg, rgba(18, 56, 61, .96) 0%, rgba(15, 107, 104, .92) 72%, rgba(178, 116, 35, .9) 100%);
        box-shadow: 0 18px 50px rgba(0, 0, 0, .25);
        margin-bottom: 1.4rem;
    }
    .hero h1 { margin: 0; font-size: 2.2rem; }
    .hero p { margin: .5rem 0 0; color: #d9efeb; }
    .eyebrow { color: #bcdbc3; text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; }
    div[data-testid="stMetric"],
    [data-testid="stForm"],
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    [data-testid="stAlert"],
    [data-testid="stJson"] {
        background: rgba(16, 35, 38, .9);
        border: 1px solid var(--mayajal-border);
        border-radius: 14px;
    }
    div[data-testid="stMetric"] { padding: 1rem; }
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricLabel"] { color: var(--mayajal-text); }
    .stTabs [data-baseweb="tab-list"] {
        background: var(--mayajal-panel);
        border: 1px solid var(--mayajal-border);
        border-radius: 12px;
        padding: .3rem;
        gap: .25rem;
    }
    .stTabs [data-baseweb="tab"] { border-radius: 9px; color: var(--mayajal-muted); }
    .stTabs [aria-selected="true"] { background: #1f5554; color: white; }
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="base-input"],
    textarea {
        background: var(--mayajal-panel-soft) !important;
        border-color: var(--mayajal-border) !important;
        color: var(--mayajal-text) !important;
    }
    input, textarea, [data-baseweb="select"] span { color: var(--mayajal-text) !important; }
    [data-baseweb="popover"], [role="listbox"] {
        background: var(--mayajal-panel-soft) !important;
        color: var(--mayajal-text) !important;
    }
    .stButton > button, .stDownloadButton > button {
        border: 1px solid #39706d;
        background: #173c3e;
        color: var(--mayajal-text);
        border-radius: 10px;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        border-color: var(--mayajal-accent);
        color: white;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(100deg, #16766f, #269b91);
        border-color: #42c7b9;
    }
    hr { border-color: var(--mayajal-border); }
    code {
        color: #d6f5f0 !important;
        background: #0b1d20 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_url(path: str) -> str:
    return f"{st.session_state.api_base_url}{path}"


def request_api(method: str, path: str, **kwargs: Any) -> requests.Response | None:
    try:
        return requests.request(
            method,
            api_url(path),
            timeout=kwargs.pop("timeout", REQUEST_TIMEOUT),
            **kwargs,
        )
    except requests.RequestException as exc:
        st.error(f"API request failed: {exc}")
        return None


def response_error(response: requests.Response | None, action: str) -> bool:
    if response is None:
        return True
    if response.ok:
        return False
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    st.error(f"{action} failed ({response.status_code}): {detail}")
    return True


def fetch_list(path: str, quiet: bool = False) -> list[dict[str, Any]]:
    response = request_api("GET", path)
    if response is None or not response.ok:
        if not quiet:
            response_error(response, "Loading data")
        return []
    try:
        result = response.json()
        return result if isinstance(result, list) else []
    except ValueError:
        if not quiet:
            st.error(f"{path} did not return JSON.")
        return []


def parse_json_object(raw: str, label: str) -> dict[str, Any] | None:
    if not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        st.error(f"{label} must be valid JSON: {exc}")
        st.stop()
    if not isinstance(value, dict):
        st.error(f"{label} must be a JSON object.")
        st.stop()
    return value


def machine_payload(
    name: str,
    image_url: str,
    os_type: str,
    restart_policy: str,
    console: bool,
    volumes: str,
    env: str,
    commands: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "imageUrl": image_url,
        "os_type": os_type,
        "restart_policy": restart_policy,
        "console": console,
        "volumes": parse_json_object(volumes, "Volumes"),
        "env": parse_json_object(env, "Environment"),
        "commands": parse_json_object(commands, "Commands"),
    }


def stream_lab_action(lab_id: str, action: str) -> None:
    status = st.empty()
    output = st.empty()
    collected = ""
    try:
        status.info(f"{action.title()} lab...")
        with requests.get(api_url(f"/labs/{lab_id}/{action}"), stream=True, timeout=None) as response:
            if response_error(response, action.title()):
                return
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    collected += f"{line}\n"
                    output.code(collected, language="text")
        status.success(f"Lab {action} completed.")
    except requests.RequestException as exc:
        status.error(f"Lab {action} failed: {exc}")


def lab_labels(labs: list[dict[str, Any]]) -> dict[str, str]:
    return {f"{lab.get('name', 'Unnamed')} | {lab['id'][:8]}": lab["id"] for lab in labs}


def machine_labels(machines: list[dict[str, Any]]) -> dict[str, str]:
    return {f"{machine.get('name', 'Unnamed')} | {machine['id'][:8]}": machine["id"] for machine in machines}


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">Mayajal control plane</div>'
        f"<h1>{title}</h1><p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )


def render_overview() -> None:
    hero("Security labs, without the command-line shuffle", "Build machines, compose labs, control runtime, and inspect results.")
    users = fetch_list("/me/", quiet=True)
    machines = fetch_list("/machines/", quiet=True)
    labs = fetch_list("/labs/", quiet=True) if users else []

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("API", "Online" if st.session_state.api_online else "Offline")
    col2.metric("Users", len(users))
    col3.metric("Machines", len(machines))
    col4.metric("Labs", len(labs))

    st.subheader("Getting started")
    st.markdown(
        """
        1. Create a user in **Users**. The API currently treats the first user as the active user.
        2. Define reusable vulnerable machines in **Machines**.
        3. Assemble and run environments in **Labs**.
        4. Correlate Suricata `eve.json` data in **Reports**.
        """
    )
    if not st.session_state.api_online:
        st.warning("The API is not reachable. Start it, then use Refresh connection in the sidebar.")


def render_users() -> None:
    hero("Users", "Create and manage the identities that own labs.")
    users = fetch_list("/me/")
    with st.expander("Create user", expanded=not users):
        with st.form("create_user"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            if st.form_submit_button("Create user", type="primary", use_container_width=True):
                response = request_api("POST", "/me/", json={"name": name, "email": email})
                if not response_error(response, "Create user"):
                    st.success("User created.")
                    st.rerun()

    if not users:
        st.info("No users yet. Create one to unlock lab management.")
        return

    st.dataframe(users, use_container_width=True, hide_index=True)
    active = users[0]
    st.caption("The API currently uses the first user as the active user.")
    with st.form("update_user"):
        st.subheader("Update active user")
        name = st.text_input("Name", value=active.get("name", ""), key="update_user_name")
        email = st.text_input("Email", value=active.get("email", ""), key="update_user_email")
        if st.form_submit_button("Save user", type="primary"):
            response = request_api("PATCH", "/me/", json={"name": name, "email": email})
            if not response_error(response, "Update user"):
                st.success("User updated.")
                st.rerun()

    st.subheader("Delete user")
    options = {f"{user['name']} | {user['email']}": user["id"] for user in users}
    selected = st.selectbox("User", options)
    confirm = st.checkbox("I understand this may also affect owned labs.", key="confirm_delete_user")
    if st.button("Delete selected user", disabled=not confirm):
        response = request_api("DELETE", f"/me/{options[selected]}")
        if not response_error(response, "Delete user"):
            st.success("User deleted.")
            st.rerun()


def machine_form(key: str, initial: dict[str, Any] | None = None) -> dict[str, Any] | None:
    initial = initial or {}
    os_options = ["Linux", "Windows", "Others"]
    restart_options = ["unless-stopped", "always", "on-failure", "no"]
    initial_os = initial.get("os_type", "Linux")
    initial_restart = str(initial.get("restart_policy", "unless-stopped")).lower().replace(" ", "-")
    if initial_os not in os_options:
        initial_os = "Others"
    if initial_restart not in restart_options:
        initial_restart = "unless-stopped"
    with st.form(key):
        col1, col2 = st.columns(2)
        name = col1.text_input("Machine name", value=initial.get("name", ""))
        image_url = col2.text_input("Docker image", value=initial.get("imageUrl", ""))
        os_type = col1.selectbox("OS type", os_options, index=os_options.index(initial_os))
        restart_policy = col2.selectbox("Restart policy", restart_options, index=restart_options.index(initial_restart))
        console = st.checkbox("Allocate console / TTY", value=initial.get("console", True))
        volumes = st.text_area("Volumes JSON", value=json.dumps(initial.get("volumes") or {}, indent=2), help='Example: {"/host/path": "/container/path"}')
        env = st.text_area("Environment JSON", value=json.dumps(initial.get("env") or {}, indent=2), help='Example: {"MODE": "training"}')
        commands = st.text_area("Commands JSON", value=json.dumps(initial.get("commands") or {}, indent=2))
        if st.form_submit_button("Save machine", type="primary", use_container_width=True):
            return machine_payload(name, image_url, os_type, restart_policy, console, volumes, env, commands)
    return None


def render_create_machine() -> None:
    hero("Create machine", "Define a reusable Docker-backed target for your security labs.")
    payload = machine_form("create_machine")
    if payload:
        response = request_api("POST", "/machines/", json=payload)
        if not response_error(response, "Create machine"):
            st.success("Machine created and Compose definition generated.")
            st.rerun()


def render_manage_machines() -> None:
    hero("Manage machines", "Review, update, and remove reusable lab targets.")
    machines = fetch_list("/machines/")
    if not machines:
        st.info("No machines available. Use Create machine to add one.")
        return
    st.dataframe(machines, use_container_width=True, hide_index=True)
    labels = machine_labels(machines)
    selected_label = st.selectbox("Machine to manage", labels)
    selected_id = labels[selected_label]
    selected = next(machine for machine in machines if machine["id"] == selected_id)
    payload = machine_form(f"edit_machine_{selected_id}", selected)
    if payload:
        response = request_api("PATCH", f"/machines/{selected_id}", json=payload)
        if not response_error(response, "Update machine"):
            st.success("Machine updated.")
            st.rerun()
    confirm = st.checkbox("Confirm machine deletion", key=f"delete_machine_{selected_id}")
    if st.button("Delete machine", disabled=not confirm):
        response = request_api("DELETE", f"/machines/{selected_id}")
        if not response_error(response, "Delete machine"):
            st.success("Machine deleted.")
            st.rerun()


def lab_form(key: str, machines: list[dict[str, Any]], initial: dict[str, Any] | None = None) -> dict[str, Any] | None:
    initial = initial or {}
    labels = machine_labels(machines)
    initial_ids = {machine.get("id") for machine in initial.get("machines", []) if isinstance(machine, dict)}
    initial_ids.update(machine["id"] for machine in machines if machine.get("lab_id") == initial.get("id"))
    defaults = [label for label, machine_id in labels.items() if machine_id in initial_ids]
    with st.form(key):
        name = st.text_input("Lab name", value=initial.get("name", ""))
        description = st.text_area("Description", value=initial.get("description") or "")
        selected = st.multiselect("Machines", labels, default=defaults)
        if st.form_submit_button("Save lab", type="primary", use_container_width=True):
            return {"name": name, "description": description or None, "machines": [labels[label] for label in selected]}
    return None


def lab_prerequisites() -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    users = fetch_list("/me/", quiet=True)
    if not users:
        st.warning("Create a user before managing labs.")
        return None
    machines = fetch_list("/machines/")
    labs = fetch_list("/labs/")
    return machines, labs


def render_create_lab() -> None:
    hero("Create lab", "Assemble reusable machines into a new isolated environment.")
    data = lab_prerequisites()
    if data is None:
        return
    machines, _ = data
    if not machines:
        st.info("Create at least one machine before assembling a lab.")
        return
    payload = lab_form("create_lab", machines)
    if payload:
        response = request_api("POST", "/labs/", json=payload)
        if not response_error(response, "Create lab"):
            st.success("Lab created.")
            st.rerun()


def render_manage_labs() -> None:
    hero("Manage labs", "Control runtime, update machine membership, and retrieve access configuration.")
    data = lab_prerequisites()
    if data is None:
        return
    machines, labs = data
    if not labs:
        st.info("No labs available. Use Create lab to add one.")
        return

    labels = lab_labels(labs)
    selected_label = st.selectbox("Lab to manage", labels)
    lab_id = labels[selected_label]
    detail_response = request_api("GET", f"/labs/{lab_id}")
    selected = detail_response.json() if detail_response is not None and detail_response.ok else next(lab for lab in labs if lab["id"] == lab_id)

    control_tab, edit_tab = st.tabs(["Runtime controls", "Edit and delete"])
    with control_tab:
        st.json(selected)
        col1, col2, col3 = st.columns(3)
        if col1.button("Start lab", type="primary", use_container_width=True):
            stream_lab_action(lab_id, "start")
        if col2.button("Stop lab", use_container_width=True):
            stream_lab_action(lab_id, "stop")
        if col3.button("Fetch config", use_container_width=True):
            response = request_api("GET", f"/labs/{lab_id}/config")
            if not response_error(response, "Fetch config"):
                st.session_state.lab_config = (lab_id, response.content)
        if st.session_state.get("lab_config", (None,))[0] == lab_id:
            st.download_button(
                "Download WireGuard config",
                data=st.session_state.lab_config[1],
                file_name=f"{lab_id}_peer.conf",
                mime="application/octet-stream",
                use_container_width=True,
            )

    with edit_tab:
        payload = lab_form(f"edit_lab_{lab_id}", machines, selected)
        if payload:
            response = request_api("PATCH", f"/labs/{lab_id}", json=payload)
            if not response_error(response, "Update lab"):
                st.success("Lab updated.")
                st.rerun()
        confirm = st.checkbox("Confirm lab deletion", key=f"delete_lab_{lab_id}")
        if st.button("Delete lab", disabled=not confirm):
            response = request_api("DELETE", f"/labs/{lab_id}")
            if not response_error(response, "Delete lab"):
                st.success("Lab deleted.")
                st.rerun()


def render_reports() -> None:
    hero("Reports", "Turn Suricata event logs into a correlated MITRE ATT&CK narrative.")
    labs = fetch_list("/labs/", quiet=True)
    source_mode = st.radio("Event source", ["Lab event log", "Upload eve.json"], horizontal=True)
    eve_path: Path | None = None
    uploaded = None
    report_name = "suricata_report.json"

    if source_mode == "Lab event log":
        if not labs:
            st.info("No labs available.")
            return
        labels = lab_labels(labs)
        selected = st.selectbox("Lab", labels, key="report_lab")
        lab_id = labels[selected]
        eve_path = ROOT_DIR / "labs" / lab_id / "logs" / "suricata" / "eve.json"
        report_name = f"{lab_id}_report.json"
        st.code(str(eve_path), language="text")
    else:
        uploaded = st.file_uploader("Upload newline-delimited Suricata JSON", type=["json"])

    attacker = st.text_input("Attacker IP override", placeholder="Optional")
    if st.button("Generate report", type="primary", use_container_width=True):
        if uploaded is not None:
            upload_dir = ROOT_DIR / ".streamlit_uploads"
            upload_dir.mkdir(exist_ok=True)
            eve_path = upload_dir / "eve.json"
            eve_path.write_bytes(uploaded.getvalue())
        if eve_path is None or not eve_path.exists():
            st.error("The selected eve.json file does not exist.")
            return
        command = [sys.executable, str(ROOT_DIR / "co.py"), str(eve_path), "--format", "json"]
        if attacker.strip():
            command.extend(["--attacker", attacker.strip()])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            st.error("Report generation failed.")
            st.code(result.stderr or result.stdout, language="text")
            return
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            st.error("The report generator returned invalid JSON.")
            st.code(result.stdout, language="text")
            return
        st.success("Report generated.")
        stats = report.get("stats", {})
        col1, col2, col3 = st.columns(3)
        col1.metric("Events", stats.get("total_events", 0))
        col2.metric("Attacker", stats.get("attacker_ip") or "Unknown")
        col3.metric("Attack phases", len(report.get("chain", [])))
        st.json(report)
        st.download_button(
            "Download JSON report",
            data=json.dumps(report, indent=2),
            file_name=report_name,
            mime="application/json",
            use_container_width=True,
        )


if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = DEFAULT_API_URL

with st.sidebar:
    st.markdown("## MAYAJAL")
    st.caption("Security lab control plane")
    api_base_url = st.text_input("API base URL", value=st.session_state.api_base_url).rstrip("/")
    st.session_state.api_base_url = api_base_url
    health = request_api("GET", "/docs", timeout=4)
    st.session_state.api_online = health is not None and health.ok
    st.success("API connected") if st.session_state.api_online else st.error("API offline")
    if st.button("Refresh connection", use_container_width=True):
        st.rerun()
    page = st.radio(
        "Navigate",
        [
            "Overview",
            "Create lab",
            "Manage labs",
            "Create machine",
            "Manage machines",
            "Users",
            "Reports",
        ],
    )
    st.caption("API docs: " + api_url("/docs"))

pages = {
    "Overview": render_overview,
    "Create lab": render_create_lab,
    "Manage labs": render_manage_labs,
    "Create machine": render_create_machine,
    "Manage machines": render_manage_machines,
    "Users": render_users,
    "Reports": render_reports,
}
pages[page]()
