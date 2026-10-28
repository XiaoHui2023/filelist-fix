@echo off
setlocal EnableExtensions
rem CI uses setup-python directly; no nested venv or editable project installation.
python -m pip install --disable-pip-version-check --force-reinstall -r tools\requirements-release.txt
if errorlevel 1 exit /b 1
python -m pip install --no-deps --force-reinstall .
if errorlevel 1 exit /b 1
call tools\download_rg_fd.bat
if errorlevel 1 exit /b 1
python tools\release_build.py
exit /b %errorlevel%
