import os
import openpyxl
import pandas as pd
import streamlit as st

def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def append_rows_to_excel(rows_data, sheet_name="Email Data", log_fn=print):
    file_path = get_secret("EXCEL_FILE_PATH", "output.xlsx")
    log_fn(f"Excel फ़ाइल ({file_path}) में डेटा सेव किया जा रहा है...")

    new_df = pd.DataFrame(rows_data)
    if new_df.empty:
        return 0

    rename_map = {
        "name": "Name",
        "email": "Email",
        "phone": "Phone",
        "query": "Query",
        "raw_subject": "Subject",
        "raw_date": "Date"
    }
    new_df = new_df.rename(columns=rename_map)

    if os.path.exists(file_path):
        with pd.ExcelWriter(file_path, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
            try:
                existing_df = pd.read_excel(file_path, sheet_name=sheet_name)
                start_row = len(existing_df) + 1
                new_df.to_excel(writer, sheet_name=sheet_name, startrow=start_row, index=False, header=False)
            except Exception:
                new_df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            new_df.to_excel(writer, sheet_name=sheet_name, index=False)

    return len(rows_data)
          
