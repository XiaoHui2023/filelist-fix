@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call "%~dp0update.bat"
  if errorlevel 1 exit /b 1
)
call "%~dp0.venv\Scripts\activate.bat"
python -m pytest
exit /b %ERRORLEVEL%
