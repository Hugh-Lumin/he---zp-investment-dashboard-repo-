@echo off
rem Refresh the Portfolios dashboard from the OneDrive-synced SharePoint workbook.
python "%~dp0scripts\refresh_dashboard.py" %*
pause
