#!/bin/bash
# =============================================================================
# run_pipeline.command — Aerospace Outreach Automation Control Center (Mac/Linux)
# =============================================================================
# Double-click this file on Mac to run the full pipeline in Terminal.
# On Linux, run:  bash run_pipeline.command
#
# Prerequisites:
#   1. Python 3.9+ installed
#   2. pip install -r requirements.txt
#   3. All API keys set in config.py
# =============================================================================

# Change to the directory where this script lives (handles double-click on Mac)
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}============================================================${RESET}"
    echo -e "${BOLD}${CYAN}  $1${RESET}"
    echo -e "${BOLD}${CYAN}============================================================${RESET}"
    echo ""
}

print_step() {
    echo -e "${BOLD}${YELLOW}▶  $1${RESET}"
}

print_ok() {
    echo -e "${GREEN}✔  $1${RESET}"
}

print_error() {
    echo -e "${RED}✘  ERROR: $1${RESET}"
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
print_header "Aerospace Outreach Automation Pipeline"

print_step "Checking Python installation …"
if ! command -v python3 &>/dev/null; then
    print_error "python3 not found. Install Python 3.9+ and try again."
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1)
print_ok "Found: $PYTHON_VERSION"

print_step "Checking required packages …"
MISSING_PACKAGES=()
python3 -c "import requests"   2>/dev/null || MISSING_PACKAGES+=("requests")
python3 -c "import anthropic"  2>/dev/null || MISSING_PACKAGES+=("anthropic")
python3 -c "import gspread"    2>/dev/null || MISSING_PACKAGES+=("gspread")
python3 -c "import google.oauth2" 2>/dev/null || MISSING_PACKAGES+=("google-auth")

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}  Installing missing packages: ${MISSING_PACKAGES[*]}${RESET}"
    pip3 install -q requests anthropic gspread google-auth google-auth-oauthlib
fi
print_ok "All packages ready."

# ---------------------------------------------------------------------------
# Check that config.py has been edited (basic guard)
# ---------------------------------------------------------------------------
print_step "Checking config.py …"
if grep -q "YOUR_PERPLEXITY_API_KEY" config.py; then
    print_error "PERPLEXITY_API_KEY is still the placeholder in config.py."
    echo "       Open config.py and fill in your API keys before running the pipeline."
    exit 1
fi
print_ok "config.py looks configured."

# Ensure data directory exists
mkdir -p data

# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------
START_TIME=$SECONDS

run_step() {
    local step_num="$1"
    local script="$2"
    local label="$3"

    print_header "Step $step_num — $label"
    python3 "$script"
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        print_error "Step $step_num failed (exit code $EXIT_CODE). Pipeline stopped."
        echo ""
        echo "Fix the issue above and re-run this script."
        exit $EXIT_CODE
    fi

    print_ok "Step $step_num complete."
}

run_step 1 "1_company_research.py"  "Company Research  (Perplexity API)"
run_step 2 "2_contact_finder.py"    "Contact Finder    (Apollo.io)"
run_step 3 "3_message_drafter.py"   "Message Drafter   (Claude API)"
run_step 4 "4_sheets_tracker.py"    "Google Sheets Tracker"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
ELAPSED=$(( SECONDS - START_TIME ))
print_header "Pipeline Complete"
echo -e "  ${GREEN}All 4 steps finished successfully in ${ELAPSED}s.${RESET}"
echo ""
echo "  Output files:"
echo "    data/companies_researched.csv"
echo "    data/contacts.csv"
echo "    data/messages_drafted.csv"
echo "    Google Sheet updated ✔"
echo ""

# Keep the terminal window open on Mac double-click
if [[ "$TERM_PROGRAM" == "" ]]; then
    echo "Press any key to close …"
    read -n 1
fi
