import streamlit as st
import requests
import subprocess
from pathlib import Path

# --------------------------------------------------
# Streamlit Page Config
# --------------------------------------------------
st.set_page_config(
    page_title="Mayajal Lab Dashboard",
    page_icon="🛡️",
    layout="centered"
)

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


# --------------------------------------------------
# Helper: Normal GET Request
# --------------------------------------------------
def normal_get_request(url):
    try:
        response = requests.get(url, timeout=30)
        return response
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to FastAPI backend. Make sure it is running.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


# --------------------------------------------------
# Helper: Streaming GET Request
# --------------------------------------------------
def stream_fastapi_response(url, action_name):
    output_box = st.empty()
    status_box = st.empty()

    full_output = ""

    try:
        status_box.info(f"{action_name} started...")

        with requests.get(url, stream=True, timeout=None) as response:
            if response.status_code != 200:
                status_box.error(f"{action_name} failed.")
                st.error(f"Error {response.status_code}: {response.text}")
                return

            for line in response.iter_lines(decode_unicode=True):
                if line:
                    full_output += line + "\n"
                    output_box.code(full_output)

            status_box.success(f"{action_name} completed successfully.")

    except requests.exceptions.ConnectionError:
        status_box.error("Could not connect to FastAPI backend.")
        st.warning("Make sure your FastAPI server is running.")

    except Exception as e:
        status_box.error("Unexpected error occurred.")
        st.error(str(e))


# --------------------------------------------------
# Helper: Load Labs
# --------------------------------------------------
def get_labs(api_base_url):
    response = normal_get_request(f"{api_base_url}/labs/")

    if response is None:
        return []

    if response.status_code != 200:
        st.error(f"Failed to load labs: {response.text}")
        return []

    try:
        return response.json()
    except Exception:
        st.error("Labs endpoint did not return valid JSON.")
        return []

# Report generatoion

def run_report_generator(lab_id):
    """
    Runs co.py using the eve.json file inside labs/{lab_id}/eve.json.
    """

    base_dir = Path(__file__).resolve().parent.parent

    co_script = base_dir / "co.py"
    lab_folder = base_dir / "labs" / str(lab_id)
    eve_file = lab_folder / "logs" / "suricata" / "eve.json"

    if not co_script.exists():
        st.error(f"co.py not found at: {co_script}")
        return None

    if not lab_folder.exists():
        st.error(f"Lab folder not found: {lab_folder}")
        return None

    if not eve_file.exists():
        st.error(f"eve.json not found inside lab folder: {eve_file}")
        return None

    try:
        result = subprocess.run(
            ["python", str(co_script), str(eve_file)],
            capture_output=True,
            text=True,
            check=False
        )

        return result

    except Exception as e:
        st.error(f"Failed to run report generator: {e}")
        return None
# --------------------------------------------------
# Sidebar Settings
# --------------------------------------------------
st.sidebar.title("⚙️ Settings")

api_base_url = st.sidebar.text_input(
    "FastAPI Base URL",
    value=DEFAULT_API_BASE_URL
).rstrip("/")

st.sidebar.info("Example: http://127.0.0.1:8000")


# --------------------------------------------------
# Main UI
# --------------------------------------------------
st.title("🛡️ Mayajal Lab Dashboard")

st.write(
    "Simple dashboard to start labs, stop labs, download lab config, "
    "and generate reports from your FastAPI backend."
)

st.divider()


# --------------------------------------------------
# Select Lab from API
# --------------------------------------------------
st.subheader("Select Lab")

labs = get_labs(api_base_url)

if not labs:
    st.warning("No labs found. Please check if your FastAPI backend is running and /Labs/ returns data.")
    st.stop()


lab_options = {}

for lab in labs:
    if isinstance(lab, dict):
        lab_id = (
            lab.get("id")
            or lab.get("labId")
            or lab.get("lab_id")
        )

        lab_name = (
            lab.get("name")
            or lab.get("title")
            or lab.get("labName")
            or f"Lab {lab_id}"
        )

        if lab_id:
            lab_options[f"{lab_name} ({lab_id})"] = lab_id

    else:
        lab_options[str(lab)] = lab


if not lab_options:
    st.error("Could not find lab IDs from the /Labs/ response.")
    st.write("Your /Labs/ response:")
    st.json(labs)
    st.stop()


selected_lab_label = st.selectbox(
    "Choose a lab",
    list(lab_options.keys())
)

selected_lab_id = lab_options[selected_lab_label]

st.success(f"Selected Lab ID: {selected_lab_id}")

st.divider()


# --------------------------------------------------
# Lab Controls
# --------------------------------------------------
st.subheader("Lab Controls")

col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Start Lab", use_container_width=True):
        start_url = f"{api_base_url}/labs/{selected_lab_id}/start"
        stream_fastapi_response(start_url, "Starting lab")

with col2:
    if st.button("⏹️ Stop Lab", use_container_width=True):
        stop_url = f"{api_base_url}/labs/{selected_lab_id}/stop"
        stream_fastapi_response(stop_url, "Stopping lab")


st.divider()


# --------------------------------------------------
# Lab Configuration
# --------------------------------------------------
st.subheader("Lab Configuration")

if st.button("⬇️ Get / Download Lab Config", use_container_width=True):
    config_url = f"{api_base_url}/labs/{selected_lab_id}/config"
    response = normal_get_request(config_url)

    if response is not None:
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")

            st.success("Lab configuration received successfully.")

            if "application/json" in content_type:
                st.json(response.json())

                st.download_button(
                    label="Download Config JSON",
                    data=response.text,
                    file_name=f"lab_{selected_lab_id}_config.json",
                    mime="application/json",
                    use_container_width=True
                )

            else:
                st.code(response.text)

                st.download_button(
                    label="Download WireGuard Config",
                    data=response.content,
                    file_name=f"lab_{selected_lab_id}_wireguard.conf",
                    mime="application/octet-stream",
                    use_container_width=True
                )

        else:
            st.error(f"Failed to get lab config: {response.text}")


st.divider()


# --------------------------------------------------
# Generate Report
# --------------------------------------------------
st.subheader("Generate Report")

if st.button("📄 Generate Report", use_container_width=True):
    with st.spinner("Generating report from eve.json..."):
        result = run_report_generator(selected_lab_id)

    if result is not None:
        if result.returncode == 0:
            st.success("Report generated successfully.")

            if result.stdout:
                st.code(result.stdout)

            report_folder = Path(__file__).parent / "labs" / str(selected_lab_id)

            possible_reports = list(report_folder.glob("*.pdf")) + list(report_folder.glob("*.html")) + list(report_folder.glob("*.txt"))

            if possible_reports:
                latest_report = max(possible_reports, key=lambda p: p.stat().st_mtime)

                st.info(f"Generated report found: {latest_report.name}")

                with open(latest_report, "rb") as file:
                    st.download_button(
                        label=f"⬇️ Download {latest_report.name}",
                        data=file,
                        file_name=latest_report.name,
                        mime="application/octet-stream",
                        use_container_width=True
                    )
            else:
                st.warning("co.py ran successfully, but no report file was found in the lab folder.")

        else:
            st.error("Report generation failed.")

            if result.stderr:
                st.code(result.stderr)

            if result.stdout:
                st.code(result.stdout)


# --------------------------------------------------
# View Lab Details
# --------------------------------------------------
st.subheader("Lab Details")

if st.button("🔍 View Selected Lab Details", use_container_width=True):
    detail_url = f"{api_base_url}/Labs/{selected_lab_id}"
    response = normal_get_request(detail_url)

    if response is not None:
        if response.status_code == 200:
            st.success("Lab details loaded.")

            try:
                st.json(response.json())
            except Exception:
                st.code(response.text)

        else:
            st.error(f"Failed to load lab details: {response.text}")


st.caption("Mayajal Capstone Lab Dashboard")