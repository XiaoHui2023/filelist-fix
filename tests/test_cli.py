from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_help_exits_zero() -> None:
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(root / "src"), "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "usage:" in proc.stdout.lower() or "usage:" in proc.stderr.lower()
