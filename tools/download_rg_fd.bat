@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

set "BIN=%CD%\tools\bin"
if not exist "%BIN%" mkdir "%BIN%"

set "RG_VER=14.1.1"
set "FD_VER=10.2.0"

if "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto arch_amd64
if "%PROCESSOR_ARCHITECTURE%"=="ARM64" goto arch_arm64
echo Unsupported PROCESSOR_ARCHITECTURE=%PROCESSOR_ARCHITECTURE%
exit /b 1

:arch_amd64
set "RG_ASSET=ripgrep-%RG_VER%-x86_64-pc-windows-msvc.zip"
set "FD_ASSET=fd-v%FD_VER%-x86_64-pc-windows-msvc.zip"
goto dl

:arch_arm64
set "RG_ASSET=ripgrep-%RG_VER%-aarch64-pc-windows-msvc.zip"
set "FD_ASSET=fd-v%FD_VER%-aarch64-pc-windows-msvc.zip"
goto dl

:dl
set "TMP=%TEMP%\filelist_fix_tools_%RANDOM%"
mkdir "%TMP%" 2>nul

echo ==^> ripgrep %RG_VER% %RG_ASSET%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$u='https://github.com/BurntSushi/ripgrep/releases/download/%RG_VER%/%RG_ASSET%';" ^
  "$o='%TMP%\rg.zip'; Invoke-WebRequest -Uri $u -OutFile $o; Expand-Archive -Path $o -DestinationPath '%TMP%\rg' -Force;" ^
  "$rg = Get-ChildItem -Path '%TMP%\rg' -Recurse -Filter rg.exe | Select-Object -First 1;" ^
  "if (-not $rg) { throw 'rg.exe not found in archive' }; Copy-Item -Force $rg.FullName '%BIN%\rg.exe'"

echo ==^> fd %FD_VER% %FD_ASSET%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$u='https://github.com/sharkdp/fd/releases/download/v%FD_VER%/%FD_ASSET%';" ^
  "$o='%TMP%\fd.zip'; Invoke-WebRequest -Uri $u -OutFile $o; Expand-Archive -Path $o -DestinationPath '%TMP%\fd' -Force;" ^
  "$fd = Get-ChildItem -Path '%TMP%\fd' -Recurse -Filter fd.exe | Select-Object -First 1;" ^
  "if (-not $fd) { throw 'fd.exe not found in archive' }; Copy-Item -Force $fd.FullName '%BIN%\fd.exe'"

rd /s /q "%TMP%" 2>nul
echo Done: %BIN%\rg.exe and %BIN%\fd.exe
endlocal
