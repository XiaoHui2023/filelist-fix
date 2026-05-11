#!/usr/bin/env bash
# 使用静态 example/run_prelude.f，在 example/generated 写出 demo_filelist.f（对应 example.bat）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$ROOT/update.sh"
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

mkdir -p "$ROOT/example/generated"
RTL="$ROOT/example/complex_rtl"
PRELUDE="$ROOT/example/run_prelude.f"
FILELIST="$ROOT/example/generated/demo_filelist.f"

abs() { (cd "$1" && pwd); }

echo "filelist-fix example: python \"$ROOT/src\" --source \"$(abs "$RTL")\" -t top_chip -p \"$PRELUDE\" -o \"$FILELIST\""
python "$ROOT/src" --source "$(abs "$RTL")" -t top_chip -p "$PRELUDE" -o "$FILELIST"
