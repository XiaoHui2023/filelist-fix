#!/usr/bin/env bash
# 一键打包：仓库根 .venv → PyInstaller（filelist_fix.spec）→ Linux 上 staticx 自解压单文件 → 组装发布压缩包。
# Windows 仅 PyInstaller，产出 dist/filelist-fix.exe，无 staticx。
# 每次 pip 对项目与打包工具 --force-reinstall，避免 .venv 残留旧依赖。
#
# 用法（仓库根）：
#   ./tools/pack.sh          Linux / macOS / Git Bash
#   bash tools/pack.sh       同上（含 Windows Git Bash）
# 依赖：无 tools/bin/rg、fd 时自动调用 download_rg_fd.sh 或 .bat；Linux staticx 需系统 patchelf（如 apt install patchelf）。
# 无 .venv 时自动创建（Linux：python3 -m venv；Windows：py -3 或 python）。
# 产物：dist/filelist-fix（Linux 经 staticx）或 dist/filelist-fix.exe；
#       另有 dist/filelist-fix-<version>-<platform>.zip 或 .tar.gz（README.md，见 tools/bundle_release.py）。
# 兼容：单文件 ABI 取决于构建机 glibc；旧 Linux 须在目标机实测 staticx 产物。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

have_posix_bins() {
  [[ -f "$ROOT/tools/bin/rg" && -f "$ROOT/tools/bin/fd" ]]
}

have_win_bins() {
  [[ -f "$ROOT/tools/bin/rg.exe" && -f "$ROOT/tools/bin/fd.exe" ]]
}

ensure_tools_bin() {
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      if have_win_bins; then
        return 0
      fi
      echo "未检测到 tools/bin/rg.exe 与 fd.exe，正在运行 tools/download_rg_fd.bat ..."
      if command -v cmd.exe >/dev/null 2>&1; then
        WIN_ROOT="$ROOT"
        if command -v cygpath >/dev/null 2>&1; then
          WIN_ROOT="$(cygpath -w "$ROOT")"
        fi
        cmd.exe //c "cd /d \"$WIN_ROOT\" && tools\\download_rg_fd.bat"
      else
        echo "错误: 当前环境无法调用 cmd.exe，请先手动执行: tools\\\\download_rg_fd.bat" >&2
        exit 1
      fi
      ;;
    *)
      if have_posix_bins; then
        return 0
      fi
      echo "未检测到 tools/bin/rg 与 fd，正在运行 tools/download_rg_fd.sh ..."
      chmod +x "$ROOT/tools/download_rg_fd.sh"
      "$ROOT/tools/download_rg_fd.sh"
      ;;
  esac
}

ensure_venv() {
  if [[ -f "$ROOT/.venv/Scripts/python.exe" ]]; then
    PYTHON_CMD=("$ROOT/.venv/Scripts/python.exe")
  elif [[ -f "$ROOT/.venv/bin/python" ]]; then
    PYTHON_CMD=("$ROOT/.venv/bin/python")
  else
    echo "未找到 .venv，正在创建 ..."
    case "$(uname -s 2>/dev/null || true)" in
      MINGW*|MSYS*|CYGWIN*|Windows_NT)
        if command -v py >/dev/null 2>&1; then
          py -3 -m venv "$ROOT/.venv"
        else
          python -m venv "$ROOT/.venv"
        fi
        PYTHON_CMD=("$ROOT/.venv/Scripts/python.exe")
        ;;
      *)
        if ! command -v python3 >/dev/null 2>&1; then
          echo "错误: 需要 python3 以创建 .venv。" >&2
          exit 1
        fi
        python3 -m venv "$ROOT/.venv"
        PYTHON_CMD=("$ROOT/.venv/bin/python")
        ;;
    esac
  fi
  echo "==> 使用虚拟环境: ${PYTHON_CMD[*]} ($("${PYTHON_CMD[@]}" -V 2>/dev/null || true))"
}

ensure_tools_bin
ensure_venv

SPEC="$ROOT/filelist_fix.spec"
if [[ ! -f "$SPEC" ]]; then
  echo "错误: 未找到 $SPEC" >&2
  exit 1
fi

"${PYTHON_CMD[@]}" -m pip install -q -U pip setuptools wheel
"${PYTHON_CMD[@]}" -m pip install -q --upgrade --force-reinstall -e .
"${PYTHON_CMD[@]}" -m pip install -q --upgrade --force-reinstall "pyinstaller>=6.0"

rm -rf "$ROOT/build" "$ROOT/dist"

echo "==> PyInstaller: $SPEC"
"${PYTHON_CMD[@]}" -m PyInstaller --clean --noconfirm "$SPEC"

if [[ -f "$ROOT/dist/filelist-fix.exe" ]]; then
  echo "完成: $ROOT/dist/filelist-fix.exe（Windows：无 staticx 步骤）"
elif [[ ! -f "$ROOT/dist/filelist-fix" ]]; then
  echo "错误: 未在 dist 找到 filelist-fix 或 filelist-fix.exe。" >&2
  exit 1
else
  case "$(uname -s 2>/dev/null || true)" in
    Linux)
      if ! command -v patchelf >/dev/null 2>&1; then
        echo "错误: Linux 下 staticx 需要系统命令 patchelf（例如: sudo apt install patchelf）。" >&2
        exit 1
      fi
      "${PYTHON_CMD[@]}" -m pip install -q --upgrade --force-reinstall staticx
      STATICX="$ROOT/.venv/bin/staticx"
      if [[ ! -x "$STATICX" ]]; then
        echo "错误: 未找到可执行的 .venv/bin/staticx。" >&2
        exit 1
      fi
      PYI_OUT="$ROOT/dist/filelist-fix"
      TMP_OUT="$ROOT/dist/.filelist-fix-staticx.tmp"
      rm -f "$TMP_OUT"
      echo "==> staticx: $PYI_OUT -> filelist-fix"
      "$STATICX" "$PYI_OUT" "$TMP_OUT"
      mv -f "$TMP_OUT" "$PYI_OUT"
      chmod +x "$PYI_OUT"
      echo "完成: $PYI_OUT（staticx 自解压包；请在目标机实测）"
      ;;
    *)
      echo "完成: $ROOT/dist/filelist-fix（非 Linux，跳过 staticx）"
      ;;
  esac
fi

echo "==> 组装发布压缩包"
"${PYTHON_CMD[@]}" "$ROOT/tools/bundle_release.py"

echo "PyInstaller 输出目录: $ROOT/dist"
