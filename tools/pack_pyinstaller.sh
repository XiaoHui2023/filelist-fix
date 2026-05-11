#!/usr/bin/env bash
# 一键：确保 tools/bin 内有 rg/fd，安装 PyInstaller（若缺），再打出 onefile 产物到 dist/filelist-fix（Windows 为 dist/filelist-fix.exe）。
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

ensure_tools_bin

if [[ -z "${PYTHON_CMD+x}" ]]; then
  if [[ -f "$ROOT/.venv/Scripts/python.exe" ]]; then
    PYTHON_CMD=("$ROOT/.venv/Scripts/python.exe")
  elif [[ -f "$ROOT/.venv/bin/python" ]]; then
    PYTHON_CMD=("$ROOT/.venv/bin/python")
  else
    echo "错误: 未在仓库根找到虚拟环境解释器（需要 .venv/Scripts/python.exe 或 .venv/bin/python）。" >&2
    echo "请先创建并安装依赖，例如: python -m venv .venv 然后 pip install -e .（在已激活的 .venv 内）。" >&2
    echo "若必须使用其它解释器，请设置环境变量 PYTHON_CMD。" >&2
    exit 1
  fi
  echo "==> 使用虚拟环境: ${PYTHON_CMD[*]}"
else
  # shellcheck disable=SC2206
  PYTHON_CMD=($PYTHON_CMD)
fi

"${PYTHON_CMD[@]}" -m pip install -q "pyinstaller>=6.0"

SPEC="$ROOT/filelist_fix.spec"
if [[ ! -f "$SPEC" ]]; then
  echo "错误: 未找到 $SPEC" >&2
  exit 1
fi

rm -rf "$ROOT/build" "$ROOT/dist"

echo "==> PyInstaller: $SPEC"
"${PYTHON_CMD[@]}" -m PyInstaller --clean --noconfirm "$SPEC"

if [[ -f "$ROOT/dist/filelist-fix.exe" ]]; then
  OUT="$ROOT/dist/filelist-fix.exe"
elif [[ -f "$ROOT/dist/filelist-fix" ]]; then
  OUT="$ROOT/dist/filelist-fix"
else
  echo "错误: 未在 dist 找到 filelist-fix 可执行文件（预期 dist/filelist-fix 或 dist/filelist-fix.exe）。" >&2
  exit 1
fi

echo "完成: $OUT"
