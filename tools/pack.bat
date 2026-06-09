@echo off
setlocal EnableExtensions
rem 一键打包：仓库根 .venv → PyInstaller（filelist_fix.spec）→ 组装发布压缩包（Windows 无 staticx）。
rem 每次 pip 对项目与打包工具 --force-reinstall，避免 .venv 残留旧依赖。
rem 用法（仓库根）：tools\pack.bat
rem 依赖：无 tools\bin\rg.exe、fd.exe 时自动调用 download_rg_fd.bat。
rem 产物：dist\filelist-fix.exe；另有 dist\filelist-fix-<version>-windows.zip（含 README.md，见 tools\bundle_release.py）。
rem Spec：仓库根 filelist_fix.spec；可执行体名 filelist-fix。
cd /d "%~dp0\.."

if exist "tools\bin\rg.exe" if exist "tools\bin\fd.exe" goto :have_bins
echo 未检测到 tools\bin\rg.exe 与 fd.exe，正在运行 tools\download_rg_fd.bat ...
call tools\download_rg_fd.bat
if errorlevel 1 exit /b 1
:have_bins

if not exist ".venv\Scripts\python.exe" (
    echo 未找到 .venv，正在创建 ...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo 错误: 无法创建 .venv，请确认已安装 Python。
        exit /b 1
    )
)

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo 错误: 未找到 %PY%
    exit /b 1
)

echo ==^> 使用虚拟环境: %PY%
"%PY%" -V

"%PY%" -m pip install -q -U pip setuptools wheel
if errorlevel 1 exit /b 1
"%PY%" -m pip install -q --upgrade --force-reinstall -e .
if errorlevel 1 exit /b 1
"%PY%" -m pip install -q --upgrade --force-reinstall "pyinstaller>=6.0"
if errorlevel 1 exit /b 1

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

set "SPEC=%CD%\filelist_fix.spec"
if not exist "%SPEC%" (
    echo 错误: 未找到 %SPEC% >&2
    exit /b 1
)

echo ==^> PyInstaller: %SPEC%
"%PY%" -m PyInstaller --clean --noconfirm "%SPEC%"
if errorlevel 1 exit /b 1

if exist "%CD%\dist\filelist-fix.exe" (
    echo 完成: %CD%\dist\filelist-fix.exe（Windows：无 staticx 步骤）
) else (
    echo 错误: 未在 dist 找到 filelist-fix.exe。 >&2
    exit /b 1
)

echo ==^> 组装发布压缩包
"%PY%" tools\bundle_release.py
if errorlevel 1 exit /b 1

echo PyInstaller 输出目录: %CD%\dist
exit /b 0
