# Aerospace Outreach Automation

A four-step pipeline that researches target aerospace companies, finds decision-maker contacts, drafts personalized outreach messages with Claude, and syncs everything to a Google Sheet tracker.

```
1_company_research.py  →  2_contact_finder.py  →  3_message_drafter.py  →  4_sheets_tracker.py
```

---

## Project Structure

```
aerospace-outreach/
├── 1_company_research.py     # Perplexity API — company intelligence
├── 2_contact_finder.py       # Apollo.io — decision-maker contacts
├── 3_message_drafter.py      # Claude API — personalized message drafts
├── 4_sheets_tracker.py       # Google Sheets — master outreach tracker
├── config.py                 # All API keys and settings (do not commit)
├── requirements.txt          # Python dependencies
├── run_pipeline.command      # Mac/Linux one-click launcher
├── run_pipeline.bat          # Windows one-click launcher
├── templates/
│   ├── default.txt
│   ├── procurement.txt
│   ├── engineering.txt
│   ├── executive.txt
│   ├── business_development.txt
│   └── operations.txt
└── data/
    ├── target_companies.csv        # INPUT — list of companies to research
    ├── companies_researched.csv    # Script 1 output
    ├── contacts.csv                # Script 2 output
    └── messages_drafted.csv        # Script 3 output
```

---

## Setup

### 1. Install Python

Python 3.9 or later is required. Download from [python.org](https://www.python.org/downloads/).

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

Open `config.py` and fill in every key:

| Key | Where to get it |
|-----|----------------|
| `PERPLEXITY_API_KEY` | [perplexity.ai](https://www.perplexity.ai) → Settings → API |
| `APOLLO_API_KEY` | Apollo dashboard → Settings → Integrations → API |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Cloud Console (see below) |
| `GOOGLE_SHEET_ID` | From your Google Sheet URL |

**Google Sheets setup:**
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable **Google Sheets API** and **Google Drive API**
3. Create a **Service Account** → download the JSON key → save as `service_account.json` in the project root
4. Copy the service account email (e.g. `bot@project.iam.gserviceaccount.com`)
5. Open your Google Sheet → Share → paste the service account email with **Editor** access
6. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`

### 4. Add your target companies

Edit `data/target_companies.csv` — one company name per row under the `company_name` column:

```csv
company_name
Acme Aerospace
Delta Propulsion Systems
Orbital Composites
```

### 5. Customize ICP criteria (optional)

In `config.py`, update the `ICP_CRITERIA` block to match your client's ideal customer profile. This is injected into the Perplexity research prompt.

### 6. Customize templates (optional)

Edit any `.txt` file in `templates/`. Templates are matched to contacts by job title keywords:

| Template | Matched titles |
|----------|---------------|
| `procurement.txt` | procurement, supply chain, sourcing, purchasing |
| `engineering.txt` | engineer, CTO, chief engineer, technical |
| `business_development.txt` | business development, partnerships, BD |
| `operations.txt` | operations, COO, VP operations |
| `executive.txt` | CEO, president, founder, owner |
| `default.txt` | fallback for all other titles |

---

## Running the Pipeline

### Option A — One-click launcher (recommended)

**Mac:** Double-click `run_pipeline.command`
*(If blocked by Gatekeeper: right-click → Open → Open)*

**Windows:** Double-click `run_pipeline.bat`

The launcher runs all four scripts in order, stops on any failure, and prints a summary.

### Option B — Run scripts individually

```bash
python 1_company_research.py
python 2_contact_finder.py
python 3_message_drafter.py
python 4_sheets_tracker.py
```

---

## Script Details

### Script 1 — `1_company_research.py`

**Input:** `data/target_companies.csv`
**Output:** `data/companies_researched.csv`

Loops through each company, sends a structured prompt to Perplexity API, and extracts:
`company_name`, `website`, `description`, `employee_count`, `headquarters`, `focus_areas`, `funding_stage`, `recent_news`, `icp_fit_notes`

---

### Script 2 — `2_contact_finder.py`

**Input:** `data/companies_researched.csv`
**Output:** `data/contacts.csv`

Queries the Apollo.io People Search API for decision-maker contacts at each company, filtered by seniority and title keywords. Returns up to `APOLLO_CONTACTS_PER_COMPANY` (default: 4) contacts per company.

Output fields: `company_name`, `contact_name`, `title`, `email`, `linkedin_url`

---

### Script 3 — `3_message_drafter.py`

**Input:** `data/contacts.csv` + `data/companies_researched.csv` + `templates/`
**Output:** `data/messages_drafted.csv`

For each contact, selects the right template by title keyword, then sends a personalized prompt to Claude with company research context. Claude returns a subject line and message body under 150 words.

Output fields: `contact_name`, `company_name`, `title`, `email`, `subject_line`, `message_body`, `template_used`

---

### Script 4 — `4_sheets_tracker.py`

**Input:** `data/contacts.csv` + `data/messages_drafted.csv`
**Output:** Google Sheet (two tabs)

Creates or updates two tabs:

**Outreach Tracker tab**
- One row per contact
- Columns: Company, Contact Name, Title, Email, LinkedIn URL, Subject Line, Personalized Message, Template Used, Status, Follow-Up Date, Notes
- Status column has a dropdown: New / Sent / Replied / Not Interested
- Follow-Up Date formula: `=IF(I{row}="Sent", TODAY()+5, "")` — auto-populates 5 days after status is set to Sent

**Summary Dashboard tab**
- Counts by status (New, Sent, Replied, Not Interested)
- Total contacts count
- Reply rate percentage

---

## Re-running the Pipeline

Each script overwrites its own output file. To refresh everything:
1. Update `data/target_companies.csv` with new or revised companies
2. Run the pipeline again (launcher or individual scripts)
3. Script 4 will sync the latest data to your Google Sheet

To run only part of the pipeline (e.g., re-draft messages without re-fetching contacts):
```bash
python 3_message_drafter.py
python 4_sheets_tracker.py
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `EnvironmentError: PERPLEXITY_API_KEY is not set` | Open `config.py` and replace the placeholder with your real key |
| `FileNotFoundError: service_account.json` | Download the Google service account key and save it to the project root |
| Apollo returns 0 contacts | Check that `APOLLO_API_KEY` is valid; some company names may need the website domain to match |
| Claude returns malformed JSON | Rare — the script retries automatically; check your `ANTHROPIC_API_KEY` if it persists |
| Google Sheet not updating | Confirm the service account email has Editor access to the sheet |

---

## Security Notes

- `config.py` and `service_account.json` are listed in `.gitignore` — they will not be committed to git.
- Never share or publish these files.
- Rotate any key that is accidentally exposed.
