"""Generate legal dependency corpora and measure the public CLI without profiling overhead."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("genvar", "typedef", "spaces", "expression", "conditional", "instances")


def source_corpus(kind: str, count: int = 4038) -> str:
    """One top module with deterministic declarations, expressions or directive blocks."""
    if kind == "genvar":
        body = [f"genvar variable{i:04d};" for i in range(count)]
    elif kind == "typedef":
        body = [f"typedef bit t{i:04d};" for i in range(count)]
    elif kind == "spaces":
        body = [" " * 19 for _ in range(count)]
    elif kind == "expression":
        body = ["genvar g;", "generate if (" + " + ".join("1" for _ in range(count * 4))
                + ") begin : selected end endgenerate"]
    elif kind == "conditional":
        body = ["`define ACTIVE 1"]
        for i in range(count // 6):
            body += ["`ifdef ACTIVE", f"wire [7:0] signal_{i};", f"assign signal_{i} = 8'd{i % 256};",
                     "`else", f"missing inactive_{i}();", "`endif"]
        body += ["child actual();", "initial $display(p::VALUE);"]
    elif kind == "instances":
        body = [f"child instance_{i}(.a((1 + (2 * 3))));" for i in range(count)]
    else:
        raise ValueError(kind)
    return "module top;\n" + "\n".join(body) + "\nendmodule\n"


def check_result(code: int, elapsed: float, limit: float, actual: list[str], expected: list[str]) -> None:
    if code != 0 or elapsed > limit or actual != expected:
        raise AssertionError(f"stress failed: exit={code}, elapsed={elapsed:.3f}s, "
                             f"limit={limit}s, actual={actual}, expected={expected}")


def run_stress(command: list[str], *, counts=(4038, 40380), repeats=3,
               kinds=KINDS, limit=10.0) -> list[dict]:
    results = []
    with tempfile.TemporaryDirectory(prefix="filelist-stress-") as temp:
        work = Path(temp)
        (work / "child.sv").write_text("module child(input a); endmodule\n")
        (work / "p.sv").write_text("package p; parameter int VALUE = 1; endpackage\n")
        for count in counts:
            for kind in kinds:
                source = source_corpus(kind, count)
                (work / "top.sv").write_text(source, encoding="utf-8")
                expected = (["child.sv", "top.sv"] if kind == "instances" else
                            ["child.sv", "p.sv", "top.sv"] if kind == "conditional" else ["top.sv"])
                for repeat in range(repeats):
                    output = work / "out.f"
                    output.write_text("old valid list\n")
                    argv = [*command, "-s", str(work), "-t", "top", "-o", str(output)]
                    started = perf_counter()
                    try:
                        cp = subprocess.run(argv, capture_output=True, timeout=limit + 2)
                    except subprocess.TimeoutExpired as exc:
                        raise AssertionError(f"stress timeout: {kind} count={count} argv={argv}") from exc
                    elapsed = perf_counter() - started
                    actual = output.read_text().splitlines()
                    check_result(cp.returncode, elapsed, limit, actual, expected)
                    result = dict(kind=kind, count=count, repeat=repeat, bytes=len(source.encode()),
                                  lines=source.count("\n"), elapsed_seconds=elapsed, argv=argv,
                                  input_sha256=hashlib.sha256(source.encode()).hexdigest(),
                                  output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
                    results.append(result)
                    print(f"{kind} {len(source.encode())} bytes: {elapsed:.3f}s", flush=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--large-count", type=int, default=40380)
    parser.add_argument("--limit", type=float, default=10)
    args = parser.parse_args()
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, str(ROOT / "src")]
    results = run_stress(command, counts=(4038, args.large_count), repeats=args.repeats, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "results": results}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
