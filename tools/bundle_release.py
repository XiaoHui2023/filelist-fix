"""Assemble versioned binary, README and approved required notices."""
from __future__ import annotations
import shutil, subprocess, tempfile, zipfile
from pathlib import Path
from release_support import ROOT, archive_name, binary_name, sha, target, version, write_json

def main() -> None:
    dist=ROOT/"dist"; executable=dist/binary_name(); notices=ROOT/"build/release-notices"
    if not executable.is_file() or not (notices/"inventory.json").is_file():
        raise RuntimeError("Missing final executable or approved notice inventory")
    with tempfile.TemporaryDirectory(prefix="filelist-bundle-") as temp:
        staging=Path(temp)
        shutil.copy2(executable,staging/executable.name)
        shutil.copy2(ROOT/"README.md",staging/"README.md")
        shutil.copytree(notices,staging/"licenses")
        manifest={"product":"filelist-fix","version":version(),"target":target(),
                  "source_sha":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                  "license_policy":"allow-required","executable":executable.name,
                  "files":{p.relative_to(staging).as_posix():sha(p) for p in staging.rglob("*") if p.is_file()}}
        write_json(staging/"release-manifest.json",manifest)
        archive=dist/archive_name()
        if archive.suffix==".zip":
            with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
                for p in sorted(staging.rglob("*")):
                    if p.is_file(): z.write(p,p.relative_to(staging).as_posix())
        else:
            shutil.make_archive(str(archive).removesuffix(".tar.gz"),"gztar",staging)
    print(archive)

if __name__=="__main__": main()
