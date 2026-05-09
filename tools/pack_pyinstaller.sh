#!/usr/bin/env bash
# 一键：确保 tools/bin 内有 rg/fd，安装 PyInstaller（若缺），再打出 onedir 产物到 dist/filelist-fix/。
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
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=(python3)
  elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=(python)
  else
    echo "错误: 未找到 python3 或 python，请设置 PYTHON_CMD" >&2
    exit 1
  fi
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

OUT="$ROOT/dist/filelist-fix"
if [[ ! -d "$OUT" ]]; then
  echo "错误: 预期输出目录不存在: $OUT" >&2
  exit 1
fi

echo "完成: $OUT"
if [[ -f "$OUT/filelist-fix.exe" ]]; then
  echo "  可执行: $OUT/filelist-fix.exe"
else
  echo "  可执行: $OUT/filelist-fix"
fi
