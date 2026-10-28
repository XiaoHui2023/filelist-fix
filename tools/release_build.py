"""Build the versioned frozen program; pack wrappers are the public build entry."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

from collect_release_notices import collect
from release_support import ROOT, binary_name


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def main() -> None:
    for folder in [ROOT / "build", ROOT / "dist"]:
        if folder.resolve().parent != ROOT.resolve() or folder.is_symlink():
            raise RuntimeError(f"Refusing unsafe build directory: {folder}")
        if folder.exists():
            shutil.rmtree(folder)
    collect(ROOT / "build/release-notices")
    run(sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "filelist_fix.spec")
    executable = ROOT / "dist" / binary_name()
    if sys.platform.startswith("linux"):
        staticx = Path(sys.executable).parent / "staticx"
        temporary = executable.with_suffix(".staticx")
        command = [str(staticx), str(executable), str(temporary)]
        cp = subprocess.run(command, cwd=ROOT)
        if cp.returncode:
            run(str(staticx), "--no-compress", str(executable), str(temporary))
        os.replace(temporary, executable)
        executable.chmod(0o755)
    run(sys.executable, "tools/run_frozen_example.py", str(executable))
    run(sys.executable, "tools/bundle_release.py")
    run(sys.executable, "tools/verify_release.py", "dist", "--run")


if __name__ == "__main__":
    main()
