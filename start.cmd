@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The Python environment is missing. Follow the setup steps in README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 (
  pause
  exit /b 1
)
echo.
echo Forex Backtest: http://127.0.0.1:8787
echo Keep this window open. Press Ctrl+C to stop the server.
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8787 --noreload
pause
