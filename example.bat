@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call "%~dp0update.bat"
  if errorlevel 1 exit /b 1
)
call "%~dp0.venv\Scripts\activate.bat"

set "ROOT=%~dp0"
set "OUT=%ROOT%example\generated"
if not exist "%OUT%" mkdir "%OUT%"

for %%I in ("%ROOT%example\complex_rtl") do set "RTL_ABS=%%~fI"

set "PRELUDE=%ROOT%example\run_prelude.f"
set "FILELIST=%OUT%\demo_filelist.f"
echo filelist-fix example: python "%ROOT%src" --source "%RTL_ABS%" -t top_chip -p "%PRELUDE%" -o "%FILELIST%"
python "%ROOT%src" --source "%RTL_ABS%" -t top_chip -p "%PRELUDE%" -o "%FILELIST%"
exit /b %ERRORLEVEL%
