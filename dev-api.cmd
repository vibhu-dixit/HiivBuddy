@echo off
cd /d "%~dp0apps\api"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
