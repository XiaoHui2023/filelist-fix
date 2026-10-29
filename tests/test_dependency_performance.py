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
    timing = tmp_path / "timing.json"
    args = ["--parse-timings", timing, "--save", tmp_path / "cache.db", "-l", tmp_path / "run.log"]
    if debug:
        args += ["--debug-dump", tmp_path / "debug"]
    run(tmp_path, *args)
    files = json.loads(timing.read_text())["files"]
    assert len(files) == 1 and not files[0]["cache_hit"]
    stages = [s["stage"] for s in files[0]["stages"]]
    for required in ["read", "join", "mask", "preprocess", "semantic", "squeeze", "instances",
                     "squeeze.comments", "squeeze.declarations", "squeeze.ports"]:
        assert stages.count(required) == 1
    assert all(s["elapsed_seconds"] >= 0 and s["status"] == "ok" for s in files[0]["stages"])
    assert "parse stage=semantic status=ok elapsed=" in (tmp_path / "run.log").read_text()
    run(tmp_path, *args)
    files = json.loads(timing.read_text())["files"]
    assert len(files) == 1 and files[0]["cache_hit"]
    assert [s["stage"] for s in files[0]["stages"]] == ["cache"]


@pytest.mark.parametrize("prelude", [False, True])
def test_deadline_preserves_old_list_and_records_failure(tmp_path, prelude):
    source = tmp_path / "top.sv"
    source.write_text(stress.source_corpus("genvar"))
    output = tmp_path / "out.f"
    output.write_bytes(b"old valid list\r\n")
    timing = tmp_path / "timing.json"
    args = ["--parse-timeout", "0.000000001", "--parse-timings", timing]
    if prelude:
        args += ["-p", source]
    cp = run(tmp_path, *args, expected=2)
    assert "timeout" in cp.stderr and "stage=" in cp.stderr and "top.sv" in cp.stderr
    assert "previous filelist preserved" in cp.stderr
    assert output.read_bytes() == b"old valid list\r\n"
    assert not list(tmp_path.glob(".filelist-*"))
    report = json.loads(timing.read_text())["files"][0]
    assert report["status"] == "failed" and "budget=" in report["error"]


def test_live_slow_warning_and_disabled_deadline(tmp_path):
    (tmp_path / "top.sv").write_text(stress.source_corpus("typedef"))
    cp = run(tmp_path, "--parse-timeout", "0", "--slow-file-seconds", "0.000001")
    assert "slow dependency extraction" in cp.stderr and "stage=" in cp.stderr
    assert (tmp_path / "out.f").read_text().splitlines() == ["top.sv"]


@pytest.mark.parametrize("value", ["-1", "nan", "inf"])
def test_invalid_timeout_rejected_without_output_change(tmp_path, value):
    (tmp_path / "top.sv").write_text("module top; endmodule\n")
    (tmp_path / "out.f").write_text("old\n")
    run(tmp_path, "--parse-timeout", value, expected=2)
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
    timing = tmp_path / "timing.json"
    run(tmp_path, "--parse-timings", timing)
    records = json.loads(timing.read_text())["files"]
    assert len(records) == 1
    reads = [s for s in records[0]["stages"] if s["stage"] == "read"]
    assert {Path(s["path"]).name for s in reads} == {"top.sv", "body.svh"}


def test_timing_output_alias_rejected_before_old_list_is_touched(tmp_path):
    (tmp_path / "top.sv").write_text("module top; endmodule\n")
    (tmp_path / "old.json").write_text("old list\n")
    cp = subprocess.run([sys.executable, str(ROOT / "src"), "-s", str(tmp_path), "-t", "top",
                         "-o", str(tmp_path / "old.json"), "--parse-timings", str(tmp_path / "old.json")],
                        capture_output=True, text=True, timeout=10)
    assert cp.returncode == 2 and "must differ" in cp.stderr
    assert (tmp_path / "old.json").read_text() == "old list\n"


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252"])
def test_timeout_diagnostic_is_searchable_in_forced_color_narrow_console(tmp_path, encoding):
    (tmp_path / "top.sv").write_text(stress.source_corpus("genvar"))
    output = tmp_path / "out.f"
    output.write_text("old\n")
    cp = subprocess.run([sys.executable, str(ROOT / "src"), "-s", str(tmp_path), "-t", "top",
                         "-o", str(output), "--parse-timeout", "0.000000001"],
                        capture_output=True, text=True, encoding=encoding, timeout=10,
                        env={**os.environ, "FORCE_COLOR": "1", "COLUMNS": "32",
                             "PYTHONIOENCODING": encoding})
    assert cp.returncode == 2
    assert "stage=preprocess" in cp.stderr and str(tmp_path / "top.sv") in cp.stderr
    assert "previous filelist preserved" in cp.stderr
    assert output.read_text() == "old\n"
