from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
from time import perf_counter

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stress_dependency_scan", ROOT / "tools/stress_dependency_scan.py")
stress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stress)


def run(work, *args, expected=0):
    cp = subprocess.run([sys.executable, str(ROOT / "src"), "-s", str(work), "-t", "top",
                         "-o", str(work / "out.f"), *map(str, args)],
                        capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert cp.returncode == expected, cp.stderr
    return cp


@pytest.mark.parametrize("kind", stress.KINDS)
def test_large_legal_corpus_public_cli(tmp_path, kind):
    (tmp_path / "top.sv").write_text(stress.source_corpus(kind))
    (tmp_path / "child.sv").write_text("module child(input a); endmodule\n")
    (tmp_path / "p.sv").write_text("package p; parameter int VALUE=1; endpackage\n")
    start = perf_counter()
    run(tmp_path)
    expected = (["child.sv", "top.sv"] if kind == "instances" else
                ["child.sv", "p.sv", "top.sv"] if kind == "conditional" else ["top.sv"])
    stress.check_result(0, perf_counter()-start, 6, (tmp_path / "out.f").read_text().splitlines(), expected)


@pytest.mark.parametrize("debug", [False, True])
def test_stage_timing_and_warm_cache(tmp_path, debug):
    (tmp_path / "top.sv").write_text(stress.source_corpus("genvar"))
    log = tmp_path / "run.log"
    args = ["--save", tmp_path / "cache.db", "-l", log]
    if debug:
        args += ["--debug-dump", tmp_path / "debug"]
    run(tmp_path, *args)
    text = log.read_text()
    for stage in ["read", "join", "mask", "preprocess", "semantic", "squeeze", "instances",
                  "squeeze.comments", "squeeze.declarations", "squeeze.ports"]:
        assert text.count(f"parse stage={stage} status=ok elapsed=") == 1
    run(tmp_path, *args)
    text = log.read_text()
    assert text.count("parse stage=cache status=ok") == 1
    assert "parse stage=semantic" not in text


def short_deadline_command(work, *args):
    # Fault injection for the internal deadline; no test-only product CLI flag.
    script = f"""import sys,runpy
sys.path.insert(0, {str(ROOT / 'src')!r})
import core.parse_monitor as monitor
Original = monitor.ParseBudget
class ShortBudget(Original):
 def __init__(self, path, seconds, observer):
  super().__init__(path, 0.000000001, observer)
monitor.ParseBudget = ShortBudget
sys.argv = {[str(ROOT / 'src'), '-s', str(work), '-t', 'top', '-o', str(work / 'out.f'), *map(str,args)]!r}
runpy.run_path({str(ROOT / 'src/__main__.py')!r}, run_name='__main__')
"""
    return [sys.executable, '-c', script]


@pytest.mark.parametrize("prelude", [False, True])
def test_deadline_preserves_old_list_and_records_failure(tmp_path, prelude):
    source = tmp_path / "top.sv"
    source.write_text(stress.source_corpus("genvar"))
    output = tmp_path / "out.f"
    output.write_bytes(b"old valid list\r\n")
    log = tmp_path / "run.log"
    args = ['-l', log, *(['-p', source] if prelude else [])]
    cp = subprocess.run(short_deadline_command(tmp_path, *args), capture_output=True, text=True, timeout=10)
    assert cp.returncode == 2 and "timeout" in cp.stderr and "stage=" in cp.stderr
    assert "previous filelist preserved" in cp.stderr
    assert output.read_bytes() == b"old valid list\r\n"
    assert not list(tmp_path.glob(".filelist-*"))
    assert "parse total status=failed" in log.read_text()


def test_progress_identifies_current_source_without_slow_warning(tmp_path):
    (tmp_path / "top.sv").write_text(stress.source_corpus("typedef"))
    cp = run(tmp_path, '-l', tmp_path / 'run.log')
    assert "slow dependency extraction" not in cp.stderr
    text = (tmp_path / 'run.log').read_text(encoding='utf-8')
    assert text.index("parse · top.sv") < text.index("parse stage=read")
    assert (tmp_path / "out.f").read_text().splitlines() == ["top.sv"]


@pytest.mark.parametrize("flag", ["--parse-timeout", "--slow-file-seconds", "--parse-timings"])
def test_removed_tuning_flags_rejected_without_output_change(tmp_path, flag):
    (tmp_path / "top.sv").write_text("module top; endmodule\n")
    (tmp_path / "out.f").write_text("old\n")
    cp = run(tmp_path, flag, '1', expected=2)
    assert 'unrecognized arguments' in cp.stderr
    assert (tmp_path / "out.f").read_text() == "old\n"


@pytest.mark.parametrize("code,elapsed,actual", [(1, .1, ["top.sv"]), (0, 100, ["top.sv"]), (0, .1, ["wrong.sv"])])
def test_stress_oracle_rejects_error_slow_and_wrong_output(code, elapsed, actual):
    with pytest.raises(AssertionError):
        stress.check_result(code, elapsed, 6, actual, ["top.sv"])


def test_stress_oracle_accepts_good_control():
    stress.check_result(0, .1, 6, ["top.sv"], ["top.sv"])


def test_failed_atomic_replace_preserves_existing_bytes(tmp_path, monkeypatch):
    import impl  # register the public write event
    from api.events.filelist_build import OnFilelistWriteAPI
    from types import SimpleNamespace
    import os
    output = tmp_path / "out.f"
    output.write_bytes(b"old valid list\r\n")
    def denied(*args):
        raise PermissionError("injected replace denial")
    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError):
        OnFilelistWriteAPI.trigger(ctx=SimpleNamespace(), output_path=output, text="new\n")
    assert output.read_bytes() == b"old valid list\r\n"
    assert not list(tmp_path.glob(".filelist-*"))


def test_include_paths_are_identified_in_phase_timings(tmp_path):
    (tmp_path / "top.sv").write_text('`include "body.svh"\nmodule top; endmodule\n')
    (tmp_path / "body.svh").write_text("`define WIDTH 8\n")
    log = tmp_path / 'run.log'
    run(tmp_path, '-l', log)
    lines = log.read_text().splitlines()
    reads = [line for line in lines if 'parse stage=read status=ok' in line]
    assert len(reads) == 2
    assert any('top.sv' in line for line in reads) and any('body.svh' in line for line in reads)


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252"])
def test_timeout_diagnostic_is_searchable_in_forced_color_narrow_console(tmp_path, encoding):
    (tmp_path / "top.sv").write_text(stress.source_corpus("genvar"))
    output = tmp_path / "out.f"
    output.write_text("old\n")
    cp = subprocess.run(short_deadline_command(tmp_path),
                        capture_output=True, text=True, encoding=encoding, timeout=10,
                        env={**os.environ, "FORCE_COLOR": "1", "COLUMNS": "32",
                             "PYTHONIOENCODING": encoding})
    assert cp.returncode == 2
    assert "stage=preprocess" in cp.stderr and str(tmp_path / "top.sv") in cp.stderr
    assert "previous filelist preserved" in cp.stderr
    assert output.read_text() == "old\n"
