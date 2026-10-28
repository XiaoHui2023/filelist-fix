"""Shared identities and byte-level checks for the release pipeline."""
from __future__ import annotations

import hashlib
import json
import platform
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = text.split("[project]", 1)[1].split("\n[", 1)[0]
    matches = re.findall(r'^version\s*=\s*"([^"\n]+)"\s*$', project, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("Expected a single project version")
    return matches[0]


def target() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "aarch64"}.get(machine)
    if system not in {"linux", "windows"} or arch is None:
        raise ValueError(f"Unsupported release target: {system}/{machine}")
    return f"{system}-{arch}"


def binary_name() -> str:
    return f"filelist-fix-{version()}-{target()}" + (".exe" if platform.system() == "Windows" else "")


def archive_name() -> str:
    return f"filelist-fix-{version()}-{target()}" + (".zip" if platform.system() == "Windows" else ".tar.gz")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_archive_path(name: str) -> bool:
    parts = name.replace("\\", "/").split("/")
    return bool(name) and not name.startswith(("/", "\\")) and not re.match(r"^[A-Za-z]:", name) and ".." not in parts


def check_assets(directory: Path, expected: list[str]) -> dict[str, str]:
    actual = sorted(p.name for p in directory.iterdir() if p.is_file())
    if actual != sorted(expected):
        raise ValueError(f"Asset set differs: actual={actual}, expected={sorted(expected)}")
    result = {}
    for name in expected:
        path = directory / name
        if not path.stat().st_size or not re.search(rf"(?<!\d){re.escape(version())}(?![\d.])", name):
            raise ValueError(f"Empty or incorrectly versioned asset: {name}")
        result[name] = sha(path)
    return result


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
