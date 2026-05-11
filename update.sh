#!/usr/bin/env bash
# 创建/使用仓库根 .venv，并 editable 安装本项目与 dev 依赖（对应 update.bat）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  elif command -v python >/dev/null 2>&1; then
    python -m venv .venv
  else
    echo "错误: 未找到 python3 或 python，无法创建虚拟环境" >&2
    exit 1
  fi
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
python -m pip install -U pip
python -m pip install -e ".[dev]"
