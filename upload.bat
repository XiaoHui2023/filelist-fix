@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
call "%~dp0.venv\Scripts\activate.bat"
python -m pip install -U pip
python -m pip install -e ".[dev]"
exit /b %ERRORLEVEL%
