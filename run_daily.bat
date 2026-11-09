@echo off
cd /d "%~dp0"
if not exist data mkdir data
rem Step 5: replace the text after = with your Google Sheet ID (leave as is to save to CSV files only)
set SHEET_ID=PASTE_SHEET_ID_HERE
set GOOGLE_SA_JSON=%~dp0service-account.json
py run.py >> data\last_run.log 2>&1
