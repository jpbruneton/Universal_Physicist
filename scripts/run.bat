@echo off
cd /d "%~dp0.."
REM Universal Physicist (main.py) — phrase to full session
REM Legacy standalone sessions: py -3 written_projects\quantum_gravity_project.py ...
REM API key: environment, or .claude\settings.json (see settings.example.json)

if "%ANTHROPIC_API_KEY%"=="" (
    echo NOTE: ANTHROPIC_API_KEY is not set in this shell.
    echo If config fails, set the key or use .claude\settings.json
)

py -3 main.py %*
