import streamlit as st
import requests

# -----------------------------
# Basic Configuration
# -----------------------------
st.set_page_config(
    page_title="Mayajal Lab Dashboard",
    page_icon="🛡️",
    layout="centered"
)

# Change this if your FastAPI backend runs on another URL/port
API_BASE_URL = "http://127.0.0.1:8000"


# -----------------------------
# Helper Functions
# -----------------------------
def get_labs():
    try:
        response = requests.get(f"{API_BASE_URL}/labs/")
        if response.status_code == 200:
            return response.json()
        st.error(f"Failed to load labs: {response.text}")
        return []
    except Exception as e:
        st.error(f"API connection error: {e}")
        return []


def get_lab(lab_id):
    try:
        response = requests.get(f"{API_BASE_URL}/labs/{lab_id}")
        return response
    except Exception as e:
        st.error(f"Error getting lab: {e}")
        return None


def start_lab(lab_id):
    try:
        return requests.get(f"{API_BASE_URL}/labs/{lab_id}/start")
    except Exception as e:
        st.error(f"Error starting lab: {e}")
        return None


def stop_lab(lab_id):
    try:
        return requests.get(f"{API_BASE_URL}/labs/{lab_id}/stop")
    except Exception as e:
        st.error(f"Error stopping lab: {e}")
        return None


def get_lab_config(lab_id):
    try:
        return requests.get(f"{API_BASE_URL}/labs/{lab_id}/config")
    except Exception as e:
        st.error(f"Error downloading config: {e}")
        return None


def generate_report(lab_id):
    """
    Change this endpoint if your report endpoint is different.
    Example possible endpoint:
    /Labs/{labId}/report
    /Labs/{labId}/generate-report
    /reports/{labId}
    """
    try:
        return requests.get(f"{API_BASE_URL}/Labs/{lab_id}/report")
    except Exception as e:
        st.error(f"Error generating report: {e}")
        return None


# -----------------------------
# UI Header
# -----------------------------
st.title("🛡️ Mayajal Lab Dashboard")
st.write("Simple interface to start, stop, download config, and generate lab reports.")

st.divider()

# -----------------------------
# API URL Setting
# -----------------------------
with st.sidebar:
    st.header("Settings")
    api_url_input = st.text_input("FastAPI Base URL", value=API_BASE_URL)
    API_BASE_URL = api_url_input.rstrip("/")

    st.info("Example: http://127.0.0.1:8000")

# -----------------------------
# Load Labs
# -----------------------------
st.subheader("Select Lab")

labs = get_labs()

if not labs:
    st.warning("No labs found or API is not reachable.")
    st.stop()

# Supports both list of dicts and simple list responses
lab_options = {}

for lab in labs:
    if isinstance(lab, dict):
        lab_id = lab.get("id") or lab.get("labId") or lab.get("lab_id")
        lab_name = lab.get("name") or lab.get("title") or f"Lab {lab_id}"
        lab_options[f"{lab_name} ({lab_id})"] = lab_id
    else:
        lab_options[str(lab)] = lab

selected_lab_label = st.selectbox("Choose a lab", list(lab_options.keys()))
selected_lab_id = lab_options[selected_lab_label]

st.success(f"Selected Lab ID: {selected_lab_id}")

st.divider()

# -----------------------------
# Lab Actions
# -----------------------------
st.subheader("Lab Controls")

col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Start Lab", use_container_width=True):
        response = start_lab(selected_lab_id)

        if response and response.status_code == 200:
            st.success("Lab started successfully.")
            st.json(response.json())
        elif response:
            st.error(f"Failed to start lab: {response.text}")

with col2:
    if st.button("⏹️ Stop Lab", use_container_width=True):
        response = stop_lab(selected_lab_id)

        if response and response.status_code == 200:
            st.success("Lab stopped successfully.")
            st.json(response.json())
        elif response:
            st.error(f"Failed to stop lab: {response.text}")

st.divider()

# -----------------------------
# Download Config
# -----------------------------
st.subheader("Lab Configuration")

if st.button("⬇️ Get Lab Config", use_container_width=True):
    response = get_lab_config(selected_lab_id)

    if response and response.status_code == 200:
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            config_data = response.json()
            st.success("Lab config loaded.")
            st.json(config_data)

            st.download_button(
                label="Download Config as JSON",
                data=response.text,
                file_name=f"lab_{selected_lab_id}_config.json",
                mime="application/json",
                use_container_width=True
            )

        else:
            st.success("Lab config ready to download.")

            st.download_button(
                label="Download Lab Config",
                data=response.content,
                file_name=f"lab_{selected_lab_id}_config.conf",
                mime="application/octet-stream",
                use_container_width=True
            )
    elif response:
        st.error(f"Failed to get config: {response.text}")

st.divider()

# -----------------------------
# Generate Report
# -----------------------------
st.subheader("Report Generation")

if st.button("📄 Generate Report", use_container_width=True):
    response = generate_report(selected_lab_id)

    if response and response.status_code == 200:
        content_type = response.headers.get("content-type", "")

        if "application/pdf" in content_type:
            st.success("Report generated successfully.")

            st.download_button(
                label="Download PDF Report",
                data=response.content,
                file_name=f"lab_{selected_lab_id}_report.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        elif "application/json" in content_type:
            st.success("Report generated.")
            st.json(response.json())

            st.download_button(
                label="Download Report JSON",
                data=response.text,
                file_name=f"lab_{selected_lab_id}_report.json",
                mime="application/json",
                use_container_width=True
            )

        else:
            st.success("Report generated.")

            st.download_button(
                label="Download Report",
                data=response.content,
                file_name=f"lab_{selected_lab_id}_report.txt",
                mime="text/plain",
                use_container_width=True
            )

    elif response:
        st.error(f"Failed to generate report: {response.text}")

st.divider()

# -----------------------------
# View Lab Details
# -----------------------------
st.subheader("Lab Details")

if st.button("🔍 View Lab Details", use_container_width=True):
    response = get_lab(selected_lab_id)

    if response and response.status_code == 200:
        st.json(response.json())
    elif response:
        st.error(f"Failed to get lab details: {response.text}")
