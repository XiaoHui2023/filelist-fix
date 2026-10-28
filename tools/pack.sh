#!/usr/bin/env bash
# Build one versioned executable and archive with required notices and frozen checks.
# Usage: ./tools/pack.sh. Linux builds PyInstaller and StaticX in this same environment.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -f tools/bin/rg || ! -f tools/bin/fd ]]; then bash tools/download_rg_fd.sh; fi
if [[ ! -f .venv/bin/python ]]; then python3 -m venv .venv; fi
PY="$ROOT/.venv/bin/python"
export PATH="$ROOT/.venv/bin:$PATH"
"$PY" -m pip install --disable-pip-version-check --force-reinstall --no-binary=pyinstaller -r tools/requirements-release.txt
"$PY" -m pip install --no-deps --force-reinstall -e .
"$PY" -m pip install 'scons==4.8.1'
"$PY" -c 'import pkg_resources, SCons; print("StaticX build prerequisites available")'
"$PY" -m pip install --no-binary=staticx --no-build-isolation 'staticx==0.14.1'
"$PY" tools/release_build.py
