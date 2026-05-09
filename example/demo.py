from __future__ import annotations

import os
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
    "torture/nested/ni_leaf.v",
    "torture/nested/nested_pyramid.sv",
    "torture/torture_dep_a.v",
    "torture/torture_dep_b.v",
    "torture/torture_anon.v",
    "torture/torture_param_leaf.v",
    "torture/torture_bind.sv",
    "torture/torture_comment_farm.v",
    "torture/torture_gen.sv",
    "torture/torture_hash_params.v",
    "torture/torture_ifdef_zoo.v",
    "torture/torture_primitives_gates.v",
    "torture/torture_timing.v",
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
    anchor = filelist_out.resolve().parent
    expected = [
        Path(os.path.relpath((rtl / rel).resolve(), anchor)).as_posix()
        for rel in EXPECTED_TOPO_ORDER
    ]
    got = [Path(p).as_posix() for p in paths]
    assert got == expected, f"filelist order mismatch\ngot:\n  {got!r}\nexp:\n  {expected!r}"


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
        "--source",
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
    print("Output:", filelist_out.resolve())
    print("OK: prelude, filelist, and golden order checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
