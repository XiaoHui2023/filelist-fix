"""Publish only the exact, already verified build-job assets."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from release_support import check_assets, version


def gh(*args: str, check: bool = True):
    return subprocess.run(["gh", *args], check=check, capture_output=True, text=True, encoding="utf-8")


def main() -> None:
    directory = Path(sys.argv[1]).resolve()
    source = os.environ["GITHUB_SHA"]
    repo = os.environ["GITHUB_REPOSITORY"]
    expected = []
    for target, suffix, archive in [("windows-x86_64", ".exe", ".zip"), ("linux-x86_64", "", ".tar.gz")]:
        stem = f"filelist-fix-{version()}-{target}"
        report = json.loads((directory / (stem + ".json")).read_text(encoding="utf-8"))
        assert report["source_sha"] == source and report["extracted_smoke"]["features"]
        assert set(report["assets"]) == {stem + suffix, stem + archive}
        from release_support import sha
        assert all(sha(directory / name) == digest for name, digest in report["assets"].items())
        expected.extend([stem + suffix, stem + archive, stem + ".json"])
    check_assets(directory, expected)
    tag = "v" + version()
    ref = gh("api", f"repos/{repo}/git/ref/tags/{tag}", check=False)
    if ref.returncode == 0:
        gh("api", "--method", "PATCH", f"repos/{repo}/git/refs/tags/{tag}", "-f", f"sha={source}", "-F", "force=true")
    else:
        if "404" not in ref.stderr:
            raise RuntimeError(ref.stderr)
        gh("api", "--method", "POST", f"repos/{repo}/git/refs", "-f", f"ref=refs/tags/{tag}", "-f", f"sha={source}")
    notes = directory.parent / "release-notes.txt"
    notes.write_text(f"Rolling release from {source}.\nWindows x86_64 and Linux x86_64; Linux uses an Ubuntu 16.04 build with StaticX.\nRequired third-party notices are included. Both final executables and extracted archives passed the full example and dependency regression smoke.\n", encoding="utf-8")
    exists = gh("release", "view", tag, "--repo", repo, check=False)
    if exists.returncode:
        gh("release", "create", tag, "--repo", repo, "--verify-tag", "--title", tag,
           "--notes-file", str(notes), *[str(directory / name) for name in expected])
    else:
        current = json.loads(gh("api", f"repos/{repo}/releases/tags/{tag}").stdout)
        for asset in current["assets"]:
            if asset["name"] not in expected:
                gh("release", "delete-asset", tag, asset["name"], "--repo", repo, "--yes")
        gh("release", "upload", tag, "--repo", repo, "--clobber", *[str(directory / name) for name in expected])
        gh("release", "edit", tag, "--repo", repo, "--notes-file", str(notes))
    published = json.loads(gh("api", f"repos/{repo}/releases/tags/{tag}").stdout)
    assert sorted(a["name"] for a in published["assets"]) == sorted(expected)
    print(json.dumps({"tag": tag, "source_sha": source, "assets": expected}, indent=2))


if __name__ == "__main__":
    main()
