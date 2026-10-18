@echo off
REM Local (non-Docker) start for Windows.
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env ( copy .env.example .env >nul )
python -m alembic upgrade head
echo Pramaan AI -^> http://localhost:8000
python -m uvicorn backend.main:app --reload --port 8000
