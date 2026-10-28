"""Inspect archive bytes and run the extracted program when requested."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import tarfile
import zipfile

from release_support import archive_name, binary_name, safe_archive_path, sha, target, version, write_json
from run_frozen_example import verify


def extract_checked(archive: Path, destination: Path) -> dict:
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            if len(names) != len(set(names)) or any(not safe_archive_path(n) for n in names):
                raise ValueError("Unsafe or duplicate ZIP entries")
            package.extractall(destination)
    else:
        with tarfile.open(archive) as package:
            members = package.getmembers()
            if any(not safe_archive_path(m.name) or m.issym() or m.islnk() for m in members):
                raise ValueError("Unsafe tar entry")
            package.extractall(destination)
    manifest = json.loads((destination / "release-manifest.json").read_text(encoding="utf-8"))
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    if actual != set(manifest["files"]) | {"release-manifest.json"}:
        raise ValueError("Archive file set differs from the manifest")
    for name, digest in manifest["files"].items():
        if not safe_archive_path(name) or sha(destination / name) != digest:
            raise ValueError(f"Archive content changed: {name}")
    if manifest["license_policy"] != "allow-required" or not (destination / "licenses/inventory.json").is_file():
        raise ValueError("Required redistribution notices missing")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve()
    executable, archive = directory / binary_name(), directory / archive_name()
    report_name = f"filelist-fix-{version()}-{target()}.json"
    actual = {p.name for p in directory.iterdir() if p.is_file()}
    if not {executable.name, archive.name} <= actual or not actual <= {executable.name, archive.name, report_name}:
        raise ValueError(f"Unexpected release assets: {actual}")
    with tempfile.TemporaryDirectory(prefix="filelist-consume-") as temp:
        manifest = extract_checked(archive, Path(temp))
        if manifest["executable"] != executable.name or sha(Path(temp) / executable.name) != sha(executable):
            raise ValueError("Standalone and archived executable differ")
        report = {"version": version(), "target": target(), "source_sha": manifest["source_sha"],
                  "assets": {p.name: sha(p) for p in [executable, archive]}, "license_policy": "allow-required"}
        if args.run:
            report["extracted_smoke"] = verify(Path(temp) / executable.name)
    write_json(directory / report_name, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
