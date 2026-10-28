"""Download this platform's published assets, verify provenance and run them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from release_support import archive_name, binary_name, sha, target, version


def gh(*args: str) -> str:
    return subprocess.check_output(["gh", *args], text=True, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    tag = "v" + version()
    ref = json.loads(gh("api", f"repos/{args.repo}/git/ref/tags/{tag}"))
    assert ref["object"]["sha"] == args.sha and ref["object"]["type"] == "commit"
    release = json.loads(gh("api", f"repos/{args.repo}/releases/tags/{tag}"))
    report_name = f"filelist-fix-{version()}-{target()}.json"
    expected = [binary_name(), archive_name(), report_name]
    assets = {a["name"]: a for a in release["assets"]}
    assert all(name in assets and assets[name]["size"] > 0 for name in expected)
    with tempfile.TemporaryDirectory(prefix="downloaded-filelist-") as temp:
        directory = Path(temp)
        for name in expected:
            gh("release", "download", tag, "--repo", args.repo, "--pattern", name, "--dir", str(directory))
            digest = assets[name].get("digest")
            if digest:
                assert digest == "sha256:" + sha(directory / name)
        report = json.loads((directory / report_name).read_text(encoding="utf-8"))
        assert report["source_sha"] == args.sha
        assert all(sha(directory / name) == digest for name, digest in report["assets"].items())
        (directory / binary_name()).chmod(0o755)
        subprocess.run([sys.executable, str(Path(__file__).with_name("verify_release.py")), str(directory), "--run"], check=True)
    print(json.dumps({"downloaded_asset_smoke": "passed", "source_sha": args.sha, "target": target()}))


if __name__ == "__main__":
    main()
