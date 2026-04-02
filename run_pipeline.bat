@echo off
REM =============================================================================
REM run_pipeline.bat — Aerospace Outreach Automation Control Center (Windows)
REM =============================================================================
REM Double-click this file to run the full pipeline in a Command Prompt window.
REM
REM Prerequisites:
REM   1. Python 3.9+ installed and added to PATH
REM   2. pip install -r requirements.txt
REM   3. All API keys set in config.py
REM =============================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   Aerospace Outreach Automation Pipeline
echo ============================================================
echo.

REM ---------------------------------------------------------------------------
REM Preflight: check Python
REM ---------------------------------------------------------------------------
echo [CHECK] Looking for Python 3 ...
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found. Install Python 3.9+ and add it to PATH.
    pause
    exit /b 1
)
FOR /F "tokens=*" %%i IN ('python --version 2^>^&1') DO set PY_VER=%%i
echo [OK]    Found: %PY_VER%

REM ---------------------------------------------------------------------------
REM Preflight: install packages if needed
REM ---------------------------------------------------------------------------
echo [CHECK] Installing / verifying required packages ...
pip install -q requests anthropic gspread google-auth google-auth-oauthlib
IF ERRORLEVEL 1 (
    echo [ERROR] pip install failed. Check your internet connection or run as Administrator.
    pause
    exit /b 1
)
echo [OK]    Packages ready.

REM ---------------------------------------------------------------------------
REM Preflight: check config.py has been edited
REM ---------------------------------------------------------------------------
echo [CHECK] Checking config.py for placeholder keys ...
findstr /c:"YOUR_PERPLEXITY_API_KEY" config.py >nul 2>&1
IF NOT ERRORLEVEL 1 (
    echo [ERROR] PERPLEXITY_API_KEY is still the placeholder in config.py.
    echo         Open config.py and fill in your API keys before running.
    pause
    exit /b 1
)
echo [OK]    config.py looks configured.

REM Ensure data directory exists
if not exist "data" mkdir data

echo.
set START_TIME=%TIME%

REM ---------------------------------------------------------------------------
REM Step 1 — Company Research
REM ---------------------------------------------------------------------------
echo ============================================================
echo   Step 1 — Company Research  (Perplexity API)
echo ============================================================
python 1_company_research.py
IF ERRORLEVEL 1 (
    echo [ERROR] Step 1 failed. Pipeline stopped.
    pause
    exit /b 1
)
echo [OK] Step 1 complete.
echo.

REM ---------------------------------------------------------------------------
REM Step 2 — Contact Finder
REM ---------------------------------------------------------------------------
echo ============================================================
echo   Step 2 — Contact Finder  (Apollo.io)
echo ============================================================
python 2_contact_finder.py
IF ERRORLEVEL 1 (
    echo [ERROR] Step 2 failed. Pipeline stopped.
    pause
    exit /b 1
)
echo [OK] Step 2 complete.
echo.

REM ---------------------------------------------------------------------------
REM Step 3 — Message Drafter
REM ---------------------------------------------------------------------------
echo ============================================================
echo   Step 3 — Message Drafter  (Claude API)
echo ============================================================
python 3_message_drafter.py
IF ERRORLEVEL 1 (
    echo [ERROR] Step 3 failed. Pipeline stopped.
    pause
    exit /b 1
)
echo [OK] Step 3 complete.
echo.

REM ---------------------------------------------------------------------------
REM Step 4 — Google Sheets Tracker
REM ---------------------------------------------------------------------------
echo ============================================================
echo   Step 4 — Google Sheets Tracker
echo ============================================================
python 4_sheets_tracker.py
IF ERRORLEVEL 1 (
    echo [ERROR] Step 4 failed. Pipeline stopped.
    pause
    exit /b 1
)
echo [OK] Step 4 complete.
echo.

REM ---------------------------------------------------------------------------
REM Done
REM ---------------------------------------------------------------------------
echo ============================================================
echo   Pipeline Complete — All 4 steps finished successfully.
echo ============================================================
echo.
echo   Output files:
echo     data\companies_researched.csv
echo     data\contacts.csv
echo     data\messages_drafted.csv
echo     Google Sheet updated
echo.
pause
