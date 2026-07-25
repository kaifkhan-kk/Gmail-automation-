import json
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def append_rows_to_sheet(rows_data, sheet_name="Email Data", log_fn=print):
    spreadsheet_id = get_secret("SPREADSHEET_ID")
    service_account_str = get_secret("GOOGLE_SERVICE_ACCOUNT_JSON")

    if not spreadsheet_id:
        raise ValueError("SPREADSHEET_ID Secrets में नहीं मिला!")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    log_fn("Google Sheets से कनेक्ट किया जा रहा है...")
    
    # Authenticate via JSON string or Service Account
    if service_account_str:
        if isinstance(service_account_str, str):
            creds_dict = json.loads(service_account_str)
        else:
            creds_dict = service_account_str
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        # Fallback to gspread default auth if configured
        creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)

    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id)

    try:
        worksheet = sheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        log_fn(f"Tab '{sheet_name}' नहीं मिला, नया Tab बनाया जा रहा है...")
        worksheet = sheet.add_worksheet(title=sheet_name, rows=100, cols=20)
        # Add Headers
        worksheet.append_row(["Name", "Email", "Phone", "Query", "Subject", "Date"])

    count = 0
    for data in rows_data:
        row = [
            data.get("name", ""),
            data.get("email", ""),
            data.get("phone", ""),
            data.get("query", ""),
            data.get("raw_subject", ""),
            data.get("raw_date", "")
        ]
        worksheet.append_row(row)
        count += 1

    return count
  
