from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from release_support import safe_archive_path
from verify_release import extract_checked


@pytest.mark.parametrize("name", ["../secret", "/absolute", "C:/private", "safe/../../escape"])
def test_archive_rejects_path_escape(name: str):
    assert not safe_archive_path(name)


def test_final_bytes_missing_notice_are_rejected(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    manifest = {"files": {}, "license_policy": "allow-required"}
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("release-manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="notices missing"):
        extract_checked(archive, tmp_path / "out")


def test_final_bytes_tampering_is_rejected(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    manifest = {"files": {"program": "0" * 64}, "license_policy": "allow-required"}
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("release-manifest.json", json.dumps(manifest))
        z.writestr("program", "changed")
    with pytest.raises(ValueError, match="content changed"):
        extract_checked(archive, tmp_path / "out")


def test_archive_without_product_design_docs_is_rejected(tmp_path):
    files = {'README.md': 'readme', 'licenses/inventory.json': '{}'}
    manifest = {'files': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
                'license_policy': 'allow-required'}
    archive = tmp_path / 'old-layout.zip'
    with zipfile.ZipFile(archive, 'w') as package:
        package.writestr('release-manifest.json', json.dumps(manifest))
        for name, text in files.items():
            package.writestr(name, text)
    with pytest.raises(ValueError, match='documentation missing'):
        extract_checked(archive, tmp_path / 'out')
