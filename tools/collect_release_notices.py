"""Collect redistribution notices for runtime packages and bundled search tools."""
from __future__ import annotations

import importlib.metadata as metadata
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

from release_support import ROOT, sha, write_json

RUNTIME = ["python-library-callback", "pydantic", "pydantic-core", "rich", "typing_extensions",
           "typing-inspection", "annotated-types", "markdown-it-py", "mdurl", "Pygments",
           "setuptools", "packaging"]


def fetch(url: str) -> bytes:
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                return response.read()
        except OSError as error:
            last = error
            if attempt < 2:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Cannot obtain required notice: {url}: {last}")


def collect(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for name in [*RUNTIME, "pyinstaller"]:
        dist = metadata.distribution(name)
        notices = []
        for relative in dist.files or []:
            if re.match(r"(?i)^(LICENSE|LICENCE|COPYING|NOTICE|AUTHORS)(?:[._-].*)?$", relative.name):
                source = Path(dist.locate_file(relative))
                if not source.is_file():
                    continue
                if ".." in relative.parts:
                    raise RuntimeError(f"Unexpected notice path in {name}: {relative}")
                destination = output / name / Path(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
                notices.append(destination.relative_to(output).as_posix())
        if not notices and name != "python-library-callback":
            raise RuntimeError(f"No redistribution text found for {name} {dist.version}")
        inventory.append({"component": name, "version": dist.version,
                          "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                          "texts": notices, "source": (
                              "https://github.com/XiaoHui2023/python-library/tree/main/packages/callback"
                              if name == "python-library-callback" else "installed distribution metadata"),
                          "action": "retain required notices" if notices else "project-owned library; included in project release authorization"})
    upstream = {
        "ripgrep-14.1.1-LICENSE-MIT.txt": "https://raw.githubusercontent.com/BurntSushi/ripgrep/14.1.1/LICENSE-MIT",
        "fd-10.2.0-LICENSE-MIT.txt": "https://raw.githubusercontent.com/sharkdp/fd/v10.2.0/LICENSE-MIT",
        "PCRE2-10.43-LICENCE.txt": "https://raw.githubusercontent.com/PCRE2Project/pcre2/pcre2-10.43/LICENCE",
        "Python-LICENSE.txt": f"https://raw.githubusercontent.com/python/cpython/v{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}/LICENSE",
    }
    if sys.platform.startswith("linux"):
        upstream["StaticX-LICENSE.txt"] = "https://raw.githubusercontent.com/JonathonReinhart/staticx/v0.14.1/LICENSE.txt"
        for name in ["libc6", "libgcc1", "libstdc++6", "musl"]:
            source = Path("/usr/share/doc") / name / "copyright"
            if source.is_file():
                destination = output / f"{name}-COPYING.txt"
                destination.write_bytes(source.read_bytes())
                inventory.append({"component": name, "texts": [destination.name], "source": str(source),
                                  "action": "retain system runtime notices"})
    for name, url in upstream.items():
        destination = output / name
        destination.write_bytes(fetch(url))
        inventory.append({"component": name, "source": url, "texts": [name],
                          "action": "retain redistribution notice", "sha256": sha(destination)})
    manifest = {"license_policy": "allow-required", "approval": "User approval on 2026-10-28",
                "components": inventory}
    write_json(output / "inventory.json", manifest)
    return manifest


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/release-notices"
    result = collect(target)
    print(json.dumps({"components": len(result["components"]), "output": str(target)}))
