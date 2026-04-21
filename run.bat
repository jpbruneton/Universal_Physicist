@echo off
REM Quantum Gravity Think Tank launcher
REM Usage: run.bat [--question "..."] [--rounds N] [--no-latex]
REM
REM Before first use, set your API key:
REM   setx ANTHROPIC_API_KEY "sk-ant-..."
REM   (then open a new terminal)

if "%ANTHROPIC_API_KEY%"=="" (
    echo ERROR: ANTHROPIC_API_KEY is not set.
    echo Run:  setx ANTHROPIC_API_KEY "sk-ant-..."
    echo Then open a new terminal window.
    exit /b 1
)
py -3 main.py %*
