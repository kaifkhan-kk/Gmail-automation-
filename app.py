"""
=============================================================
  app.py — Gmail → Google Sheets / Excel Automation UI
=============================================================
Run with:  streamlit run app.py
"""

import logging
import time
from io import StringIO

import streamlit as st
import pandas as pd

# ---------------------------------------------------------------------------
# Streamlit Secrets Wrapper (Replaces config.py)
# ---------------------------------------------------------------------------
def get_secret(key: str, default: str = "") -> str:
    """Safely fetch keys from Streamlit Cloud Secrets."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

# Load configuration directly from Streamlit Secrets
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
GMAIL_USER_EMAIL = get_secret("GMAIL_USER_EMAIL")
GMAIL_APP_PASSWORD = get_secret("GMAIL_APP_PASSWORD")
SERVICE_ACCOUNT_INFO = get_secret("GOOGLE_SERVICE_ACCOUNT_JSON")
SPREADSHEET_ID = get_secret("SPREADSHEET_ID")
EXCEL_FILE_PATH = get_secret("EXCEL_FILE_PATH", "output.xlsx")
GMAIL_MAX_EMAILS = int(get_secret("GMAIL_MAX_EMAILS", "10"))

def validate_config(destination: str) -> list[str]:
    """Validate required secrets based on the chosen destination."""
    errors = []
    if not GEMINI_API_KEY:
        errors.append("❌ GEMINI_API_KEY is missing in Secrets.")
    if not GMAIL_USER_EMAIL:
        errors.append("❌ GMAIL_USER_EMAIL is missing in Secrets.")
    if not GMAIL_APP_PASSWORD:
        errors.append("❌ GMAIL_APP_PASSWORD is missing in Secrets.")

    if destination == "Google Sheets":
        if not SPREADSHEET_ID:
            errors.append("❌ SPREADSHEET_ID is missing in Secrets.")
    return errors

# Local modules
from gmail_client import fetch_unread_emails
from ai_parser import parse_emails
from sheets_client import append_rows_to_sheet
from excel_client import append_rows_to_excel

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Gmail Data Entry Automation",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_buffer = StringIO()
logging.basicConfig(
    stream=log_buffer,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)

if "run_logs" not in st.session_state:
    st.session_state.run_logs: list[str] = []

if "parsed_data" not in st.session_state:
    st.session_state.parsed_data: list[dict] = []

if "last_run_status" not in st.session_state:
    st.session_state.last_run_status: str | None = None


def _log(msg: str) -> None:
    """Append a message to the per-run log list."""
    st.session_state.run_logs.append(msg)


# ---------------------------------------------------------------------------
# Sidebar — configuration overview
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuration")
    st.markdown("All credentials come from **Streamlit Secrets**.")

    st.divider()
    st.subheader("Secret Status")

    def _status(label: str, value: str) -> None:
        icon = "✅" if value else "❌"
        st.write(f"{icon} `{label}`")

    _status("GEMINI_API_KEY", GEMINI_API_KEY)
    _status("GMAIL_USER_EMAIL", GMAIL_USER_EMAIL)
    _status("GMAIL_APP_PASSWORD", GMAIL_APP_PASSWORD)
    _status("GOOGLE_SERVICE_ACCOUNT_JSON", "set" if SERVICE_ACCOUNT_INFO else "")
    _status("SPREADSHEET_ID", SPREADSHEET_ID)
    _status("EXCEL_FILE_PATH", EXCEL_FILE_PATH)

    st.divider()
    st.subheader("Gmail Settings")
    st.caption(f"Fetching up to **{GMAIL_MAX_EMAILS}** unread emails.")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("📧 Gmail → Data Entry Automation")
st.markdown(
    "Automatically fetch unread Gmail messages, parse them with **Gemini AI**, "
    "and append structured rows to **Google Sheets** or **Excel**."
)

st.divider()

# Destination selector
col_left, col_right = st.columns([2, 3])

with col_left:
    st.subheader("1. Choose Destination")
    destination = st.selectbox(
        "Where should the data go?",
        options=["Google Sheets", "MS Excel (.xlsx)"],
        help="Select the output format for the extracted email data.",
    )

    if destination == "Google Sheets":
        sheet_tab = st.text_input(
            "Sheet tab name",
            value="Email Data",
            help="The worksheet tab inside your Google Sheet.",
        )
    else:
        sheet_tab = st.text_input(
            "Excel worksheet name",
            value="Email Data",
            help="The sheet tab inside the Excel workbook.",
        )

    st.subheader("2. Run")
    run_button = st.button(
        "▶️ Run Automation",
        type="primary",
        use_container_width=True,
        help="Fetch unread emails, parse with Gemini, and write to the chosen destination.",
    )

# Right column: preview
with col_right:
    if st.session_state.last_run_status == "success" and st.session_state.parsed_data:
        st.subheader("📊 Last Run — Parsed Data Preview")
        df = pd.DataFrame(st.session_state.parsed_data)[
            ["name", "email", "phone", "query", "raw_subject", "raw_date"]
        ]
        df.columns = ["Name", "Email", "Phone", "Query", "Subject", "Date"]
        st.dataframe(df, use_container_width=True, height=260)
    elif st.session_state.last_run_status == "error":
        st.error("Last run failed — see execution log below.")
    else:
        st.info(
            "Results will appear here after a successful run.\n\n"
            "Make sure all required Secrets are set (check the sidebar ✅)."
        )

# Execution log
st.divider()
st.subheader("🪵 Execution Log")
log_placeholder = st.empty()

if st.session_state.run_logs:
    log_placeholder.code("\n".join(st.session_state.run_logs), language="")

# ---------------------------------------------------------------------------
# Run automation logic
# ---------------------------------------------------------------------------
if run_button:
    st.session_state.run_logs = []
    st.session_state.parsed_data = []
    st.session_state.last_run_status = None

    errors = validate_config(destination)
    if errors:
        for err in errors:
            _log(err)
        _log("⛔ Please fix the above issues in Streamlit Secrets and try again.")
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")
        st.session_state.last_run_status = "error"
        st.rerun()

    # Step 1: Fetch emails
    try:
        _log("=" * 55)
        _log("STEP 1 — Fetching unread emails from Gmail…")
        _log("=" * 55)
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")

        emails = fetch_unread_emails(log_fn=_log)
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")

        if not emails:
            _log("📭 No unread emails found. Nothing to process.")
            log_placeholder.code("\n".join(st.session_state.run_logs), language="")
            st.session_state.last_run_status = "success"
            st.rerun()

    except Exception as exc:
        _log(f"❌ Gmail error: {exc}")
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")
        st.session_state.last_run_status = "error"
        st.rerun()

    # Step 2: Parse with Gemini
    try:
        _log("")
        _log("=" * 55)
        _log("STEP 2 — Parsing emails with Gemini AI…")
        _log("=" * 55)
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")

        parsed = parse_emails(emails, log_fn=_log)
        st.session_state.parsed_data = parsed
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")

    except Exception as exc:
        _log(f"❌ Gemini parsing error: {exc}")
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")
        st.session_state.last_run_status = "error"
        st.rerun()

    # Step 3: Write to destination
    try:
        _log("")
        _log("=" * 55)
        _log(f"STEP 3 — Writing to {destination}…")
        _log("=" * 55)
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")

        if destination == "Google Sheets":
            count = append_rows_to_sheet(parsed, sheet_name=sheet_tab, log_fn=_log)
        else:
            count = append_rows_to_excel(parsed, sheet_name=sheet_tab, log_fn=_log)

        _log("")
        _log(f"🎉 Done! {count} row(s) successfully written to {destination}.")
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")
        st.session_state.last_run_status = "success"

    except Exception as exc:
        _log(f"❌ Write error: {exc}")
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")
        st.session_state.last_run_status = "error"

    st.rerun()

st.divider()
st.caption("Gmail Data Entry Automation · Powered by Gemini AI")
