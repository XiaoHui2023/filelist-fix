from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

EXPECTED_TOPO_ORDER = (
    "hier/dual_mods.sv",
    "hier/leaf_alu.v",
    "hier/leaf_mem.v",
    "hier/mid_math.v",
    "hier/mid_memctl.v",
    "top_chip.v",
)

_INCDIR_LINE = re.compile(r'^\+incdir\+"([^"]+)"\s*$')


def _assert_prelude(prelude: Path, incs: list[Path]) -> None:
    lines = [
        ln.strip()
        for ln in prelude.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert lines[:3] == [
        "+define+WITH_DUAL=1",
        "+define+USE_CELLS=1",
        "+define+USE_CELLDEFINE=1",
    ]
    assert len(lines) == 3 + len(incs)
    for i, d in enumerate(incs):
        m = _INCDIR_LINE.match(lines[3 + i])
        assert m is not None, lines[3 + i]
        assert Path(m.group(1)).resolve() == d.resolve()


def _assert_filelist(rtl: Path, filelist_out: Path) -> None:
    paths = [
        ln.strip()
        for ln in filelist_out.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    expected = [(rtl / rel).resolve() for rel in EXPECTED_TOPO_ORDER]
    got = [Path(p).resolve() for p in paths]
    assert got == expected, f"filelist 与黄金序不一致\ngot:\n  {got!r}\nexp:\n  {expected!r}"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    rtl = root / "example" / "complex_rtl"
    out_dir = root / "example" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    incs = [rtl, rtl / "common", rtl / "hier", rtl / "pieces"]
    prelude = out_dir / "run_prelude.f"
    pl_lines = [
        "+define+WITH_DUAL=1",
        "+define+USE_CELLS=1",
        "+define+USE_CELLDEFINE=1",
    ]
    for d in incs:
        pl_lines.append(f'+incdir+"{d.resolve()}"')
    prelude.write_text("\n".join(pl_lines) + "\n", encoding="utf-8")
    _assert_prelude(prelude, incs)

    filelist_out = out_dir / "demo_filelist.f"
    cmd = [
        sys.executable,
        str(root / "src"),
        str(rtl.resolve()),
        "-t",
        "top_chip",
        "-p",
        str(prelude.resolve()),
        "-o",
        str(filelist_out.resolve()),
    ]
    print("filelist-fix example:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(root))
    _assert_filelist(rtl, filelist_out)
    print("输出:", filelist_out.resolve())
    print("断言通过：prelude 与 filelist 与黄金序一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
