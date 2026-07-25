"""
=============================================================
  app.py — Gmail → Google Sheets / Excel Automation UI
=============================================================
Run with:  streamlit run app.py  (port is set in .streamlit/config.toml)

Workflow:
  1. Select destination (Google Sheets or Excel)
  2. Click "Run Automation"
  3. The app fetches unread Gmail messages, parses them with
     Gemini AI, and appends structured rows to the chosen target.
"""

import logging
import time
from io import StringIO

import streamlit as st
import pandas as pd

# Local modules — all credentials come from config.py / Replit Secrets
import config
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
# Logging — captured to a StringIO buffer so we can display it in the UI
# ---------------------------------------------------------------------------
log_buffer = StringIO()
logging.basicConfig(
    stream=log_buffer,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)

# Collect per-run messages for the live log widget
if "run_logs" not in st.session_state:
    st.session_state.run_logs: list[str] = []

if "parsed_data" not in st.session_state:
    st.session_state.parsed_data: list[dict] = []

if "last_run_status" not in st.session_state:
    st.session_state.last_run_status: str | None = None  # "success" | "error" | None


def _log(msg: str) -> None:
    """Append a message to the per-run log list."""
    st.session_state.run_logs.append(msg)


# ---------------------------------------------------------------------------
# Sidebar — configuration overview
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuration")
    st.markdown("All credentials come from **Replit Secrets**. See the guide below.")

    st.divider()
    st.subheader("Secret Status")

    def _status(label: str, value: str) -> None:
        icon = "✅" if value else "❌"
        st.write(f"{icon} `{label}`")

    _status("GEMINI_API_KEY", config.GEMINI_API_KEY)
    _status("GMAIL_USER_EMAIL", config.GMAIL_USER_EMAIL)
    _status("GMAIL_APP_PASSWORD", config.GMAIL_APP_PASSWORD)
    _status("GOOGLE_SERVICE_ACCOUNT_JSON", "set" if config.SERVICE_ACCOUNT_INFO else "")
    _status("SPREADSHEET_ID", config.SPREADSHEET_ID)
    _status("EXCEL_FILE_PATH", config.EXCEL_FILE_PATH)

    st.divider()
    st.subheader("Gmail Settings")
    st.caption(f"Fetching up to **{config.GMAIL_MAX_EMAILS}** unread emails.")
    st.caption("Set `GMAIL_MAX_EMAILS` to change this limit.")

    st.divider()
    with st.expander("📖 Setup Guide", expanded=False):
        st.markdown(
            """
### Where to paste your keys

Open **Replit → Tools → Secrets** and add:

| Secret Name | What to paste |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `GMAIL_USER_EMAIL` | Your full Gmail address |
| `GMAIL_APP_PASSWORD` | A 16-char Gmail App Password |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON of your service account key |
| `SPREADSHEET_ID` | The ID from your Google Sheet URL |
| `EXCEL_FILE_PATH` | *(optional)* e.g. `output.xlsx` |

---

### Gmail App Password
1. Go to [myaccount.google.com](https://myaccount.google.com) → **Security**
2. Enable **2-Step Verification**
3. Search for **App passwords**
4. Create one → label it "Replit"
5. Paste the 16-character code into `GMAIL_APP_PASSWORD`

---

### Google Service Account (for Sheets)
1. [console.cloud.google.com](https://console.cloud.google.com) → New Project
2. Enable **Google Sheets API** + **Google Drive API**
3. **IAM & Admin → Service Accounts** → Create
4. Download the JSON key
5. Paste the **entire JSON** into `GOOGLE_SERVICE_ACCOUNT_JSON`
6. **Share your Google Sheet** with the `client_email` from that JSON
            """
        )

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("📧 Gmail → Data Entry Automation")
st.markdown(
    "Automatically fetch unread Gmail messages, parse them with **Gemini AI**, "
    "and append structured rows to **Google Sheets** or **Excel**."
)

st.divider()

# ── Destination selector ──────────────────────────────────────────────────
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

# ── Right column: live preview / results ─────────────────────────────────
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

# ── Execution log ─────────────────────────────────────────────────────────
st.divider()
st.subheader("🪵 Execution Log")
log_placeholder = st.empty()

if st.session_state.run_logs:
    log_placeholder.code("\n".join(st.session_state.run_logs), language="")

# ---------------------------------------------------------------------------
# Run automation logic
# ---------------------------------------------------------------------------
if run_button:
    # Reset state for a fresh run
    st.session_state.run_logs = []
    st.session_state.parsed_data = []
    st.session_state.last_run_status = None

    # Validate config before doing any network work
    errors = config.validate_config(destination)
    if errors:
        for err in errors:
            _log(err)
        _log("⛔ Please fix the above issues in Replit Secrets and try again.")
        log_placeholder.code("\n".join(st.session_state.run_logs), language="")
        st.session_state.last_run_status = "error"
        st.rerun()

    # ── Step 1: Fetch emails ──────────────────────────────────────────────
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

    # ── Step 2: Parse with Gemini ─────────────────────────────────────────
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

    # ── Step 3: Write to destination ──────────────────────────────────────
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

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Gmail Data Entry Automation · Credentials managed via Replit Secrets · "
    "Powered by Gemini AI, gspread, and openpyxl"
        )
