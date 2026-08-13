@echo off
rem Refresh the Portfolios dashboard: model weights from the OneDrive-synced
rem SharePoint workbook, then the daily market data (Trustnet factsheets and
rem performance, FT macro articles, AI macro summary).
python "%~dp0scripts\refresh_dashboard.py" %*
python "%~dp0scripts\fetch_market_data.py"
pause
