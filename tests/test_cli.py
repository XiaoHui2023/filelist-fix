from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_main_zero_exit() -> None:
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(root / "src"), "--version"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "0.0.0" in proc.stdout
