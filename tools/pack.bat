@echo off
setlocal EnableExtensions
rem Build one versioned Windows executable and archive, then run frozen/consumer checks.
rem Usage: tools\pack.bat. Required notices are included under the approved project policy.
cd /d "%~dp0\.."
if not exist "tools\bin\rg.exe" call tools\download_rg_fd.bat
if errorlevel 1 exit /b 1
if not exist "tools\bin\fd.exe" call tools\download_rg_fd.bat
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --force-reinstall -r tools\requirements-release.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install --no-deps --force-reinstall -e .
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\release_build.py
exit /b %errorlevel%
