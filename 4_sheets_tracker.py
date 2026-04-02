#!/usr/bin/env python3
"""
4_sheets_tracker.py — Google Sheets Outreach Tracker
======================================================
Reads all three output CSVs and populates a Google Sheet with:
  • "Outreach Tracker" tab — one row per contact, full pipeline data
  • "Summary Dashboard" tab — counts by status

Prerequisites:
  1. Enable Google Sheets API in Google Cloud Console
  2. Create a Service Account and download the JSON key
  3. Share the target Google Sheet with the service account email
  4. Set GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID in config.py

Run:
    python 4_sheets_tracker.py
"""

import csv
import os
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

import config

# ---------------------------------------------------------------------------
# Google Sheets auth
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheets_client() -> gspread.Client:
    """Authenticate and return an authorized gspread client."""
    if not os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_JSON):
        raise FileNotFoundError(
            f"Service account key not found: {config.GOOGLE_SERVICE_ACCOUNT_JSON}\n"
            "Download it from Google Cloud Console and place it in the project root."
        )
    creds  = Credentials.from_service_account_file(config.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_worksheet(spreadsheet: gspread.Spreadsheet, title: str, rows: int = 1000, cols: int = 20) -> gspread.Worksheet:
    """Return an existing worksheet by title or create a new one."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"Warning: {path} not found — skipping.")
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_tracker_rows(contacts: list[dict], messages: list[dict]) -> list[list]:
    """
    Merge contacts.csv and messages_drafted.csv into tracker rows.
    Keyed on (company_name, contact_name).
    """
    # Index messages by (company, name)
    msg_index: dict[tuple, dict] = {}
    for m in messages:
        key = (m.get("company_name", "").strip().lower(), m.get("contact_name", "").strip().lower())
        msg_index[key] = m

    rows = []
    for c in contacts:
        company = c.get("company_name", "").strip()
        name    = c.get("contact_name", "").strip()
        key     = (company.lower(), name.lower())

        msg = msg_index.get(key, {})

        rows.append([
            company,
            name,
            c.get("title", ""),
            c.get("email", ""),
            c.get("linkedin_url", ""),
            msg.get("subject_line", ""),
            msg.get("message_body", ""),
            msg.get("template_used", ""),
            "New",           # Status — default
            "",              # Follow-Up Date — formula added below
            "",              # Notes — blank for manual entry
        ])

    return rows


# ---------------------------------------------------------------------------
# Tracker tab
# ---------------------------------------------------------------------------

TRACKER_HEADERS = [
    "Company",
    "Contact Name",
    "Title",
    "Email",
    "LinkedIn URL",
    "Subject Line",
    "Personalized Message",
    "Template Used",
    "Status",
    "Follow-Up Date",
    "Notes",
]

STATUS_OPTIONS = ["New", "Sent", "Replied", "Not Interested"]


def apply_status_dropdown(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet, last_data_row: int) -> None:
    """
    Apply Status dropdown validation via raw Sheets API batchUpdate.
    Works on all gspread versions (v3 / v5 / v6) without adjustment.
    """
    sheet_id = ws.id
    body = {
        "requests": [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId":          sheet_id,
                        "startRowIndex":    1,              # row 2, 0-based
                        "endRowIndex":      last_data_row,  # exclusive upper bound
                        "startColumnIndex": 8,              # col I, 0-based
                        "endColumnIndex":   9,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": opt} for opt in STATUS_OPTIONS
                            ],
                        },
                        "showCustomUi": True,
                        "strict":       True,
                    },
                }
            }
        ]
    }
    spreadsheet.batch_update(body)


def auto_resize_columns(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet, num_cols: int) -> None:
    """Auto-resize all columns to fit their content via raw Sheets API."""
    spreadsheet.batch_update({
        "requests": [
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId":    ws.id,
                        "dimension":  "COLUMNS",
                        "startIndex": 0,
                        "endIndex":   num_cols,
                    }
                }
            }
        ]
    })


def write_tracker_tab(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet, rows: list[list]) -> None:
    """
    Write headers + data rows to the Outreach Tracker tab.
    Applies data validation (Status dropdown) and follow-up date formula.
    """
    print(f"  Writing {len(rows)} rows to '{config.SHEET_TAB_TRACKER}' …")

    # Clear existing content and write headers + data in one batch
    all_data = [TRACKER_HEADERS] + rows
    ws.clear()
    ws.update(range_name="A1", values=all_data, value_input_option="USER_ENTERED")

    # Bold + background color for header row
    ws.format("A1:K1", {
        "textFormat":      {"bold": True},
        "backgroundColor": {"red": 0.20, "green": 0.33, "blue": 0.58},
        "textFormat":      {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
    })

    # Freeze header row
    ws.freeze(rows=1)

    if rows:
        last_data_row = len(rows) + 1   # +1 for header row

        # Status dropdown — uses raw API so it works on every gspread version
        print("    Applying Status dropdown …")
        apply_status_dropdown(spreadsheet, ws, last_data_row)

        # Follow-up date formula: =IF(I{row}="Sent", TODAY()+5, "")
        # value_input_option="USER_ENTERED" ensures Google Sheets parses these as formulas
        follow_range          = f"J2:J{last_data_row}"
        follow_up_formulas    = [[f'=IF(I{r}="Sent",TODAY()+5,"")'] for r in range(2, last_data_row + 1)]
        ws.update(range_name=follow_range, values=follow_up_formulas, value_input_option="USER_ENTERED")

        # Auto-resize all columns to fit content
        print("    Auto-resizing columns …")
        auto_resize_columns(spreadsheet, ws, len(TRACKER_HEADERS))

    print(f"  Tracker tab complete.")


# ---------------------------------------------------------------------------
# Summary tab
# ---------------------------------------------------------------------------

def write_summary_tab(ws: gspread.Worksheet, tracker_ws: gspread.Worksheet) -> None:
    """Write a summary dashboard that counts rows by Status."""
    print(f"  Writing '{config.SHEET_TAB_SUMMARY}' …")

    today_str = date.today().strftime("%B %d, %Y")
    tracker_name = config.SHEET_TAB_TRACKER

    summary_data = [
        ["Outreach Summary Dashboard", ""],
        [f"Last Updated: {today_str}", ""],
        ["", ""],
        ["Status", "Count"],
        ["New",          f"=COUNTIF('{tracker_name}'!I:I,\"New\")"],
        ["Sent",         f"=COUNTIF('{tracker_name}'!I:I,\"Sent\")"],
        ["Replied",      f"=COUNTIF('{tracker_name}'!I:I,\"Replied\")"],
        ["Not Interested", f"=COUNTIF('{tracker_name}'!I:I,\"Not Interested\")"],
        ["", ""],
        ["Total Contacts", f"=COUNTA('{tracker_name}'!B:B)-1"],
        ["Reply Rate",   f"=IFERROR(COUNTIF('{tracker_name}'!I:I,\"Replied\")/COUNTIF('{tracker_name}'!I:I,\"Sent\"),0)"],
    ]

    ws.clear()
    ws.update(range_name="A1", values=summary_data)

    # Formatting
    ws.format("A1",   {"textFormat": {"bold": True, "fontSize": 14}})
    ws.format("A4:B4", {"textFormat": {"bold": True}})
    ws.format("B11",  {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
    ws.freeze(rows=1)

    print("  Summary tab complete.")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    # Validate config
    if config.GOOGLE_SHEET_ID == "YOUR_GOOGLE_SHEET_ID":
        raise EnvironmentError(
            "GOOGLE_SHEET_ID is not set in config.py. "
            "Open your Google Sheet, copy the ID from the URL, and paste it in config.py."
        )

    print("Loading CSV data …")
    contacts = load_csv(config.CONTACTS_CSV)
    messages = load_csv(config.MESSAGES_DRAFTED_CSV)

    if not contacts:
        print("No contacts found. Run scripts 1–3 first.")
        return

    tracker_rows = build_tracker_rows(contacts, messages)
    print(f"Prepared {len(tracker_rows)} tracker rows.\n")

    print("Connecting to Google Sheets …")
    gc          = get_sheets_client()
    spreadsheet = gc.open_by_key(config.GOOGLE_SHEET_ID)
    print(f"Opened: {spreadsheet.title}\n")

    # Write Tracker tab
    tracker_ws = get_or_create_worksheet(spreadsheet, config.SHEET_TAB_TRACKER)
    write_tracker_tab(spreadsheet, tracker_ws, tracker_rows)

    # Write Summary tab
    summary_ws = get_or_create_worksheet(spreadsheet, config.SHEET_TAB_SUMMARY)
    write_summary_tab(summary_ws, tracker_ws)

    sheet_url = f"https://docs.google.com/spreadsheets/d/{config.GOOGLE_SHEET_ID}"
    print(f"\nDone. Open your sheet: {sheet_url}")


if __name__ == "__main__":
    main()
