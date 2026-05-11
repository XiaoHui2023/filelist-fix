#!/usr/bin/env bash
# 在 .venv 中运行示例 demo.py（对应 example.bat）；若无 venv 则先执行 update.sh。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$ROOT/update.sh"
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
python "$ROOT/example/demo.py" "$@"
