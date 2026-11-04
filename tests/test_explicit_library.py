from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
UDP='primitive shared_udp(q,a);\noutput q; input a;\ntable\n0 : 0;\n1 : 1;\nendtable\nendprimitive\n'


def cli(work,*extra,expected=0):
    args=[sys.executable,str(ROOT/'src'),'-s',str(work),'-t','top','-p',str(work/'pre.f'),'-o',str(work/'out.f'),*map(str,extra)]
    env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'}
    cp=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',env=env,timeout=20)
    assert cp.returncode==expected,cp.stderr
    return (work/'out.f').read_text().splitlines() if expected==0 else cp


def fixture(work,source=UDP):
    (work/'a.v').write_text(source)
    (work/'b.v').write_text(source)
    (work/'pre.f').write_text('-v a.v\n-v b.v\n')
    (work/'top.sv').write_text('module top; wire q,a; shared_udp u(q,a); endmodule\n')


@pytest.mark.parametrize('source',[UDP,'module shared_udp(output q,input a); assign q=a; endmodule\n'])
def test_duplicate_explicit_libraries_keep_prefix_and_cold_warm_identity(tmp_path,source):
    fixture(tmp_path,source)
    for _ in range(2):
        assert cli(tmp_path,'--save',tmp_path/'cache.db')==['-v a.v','-v b.v','top.sv']


def test_ordinary_duplicates_are_still_errors(tmp_path):
    fixture(tmp_path)
    (tmp_path/'pre.f').write_text('a.v\nb.v\n')
    (tmp_path/'out.f').write_bytes(b'previous\r\n')
    cp=cli(tmp_path,expected=1)
    assert 'Duplicate definition' in cp.stderr
    assert (tmp_path/'out.f').read_bytes()==b'previous\r\n'


def test_ordinary_definition_wins_over_library_candidate(tmp_path):
    fixture(tmp_path)
    (tmp_path/'top.sv').write_text('module top; wire q,a; shared_udp u(q,a); endmodule\n'+UDP)
    assert cli(tmp_path)==['-v a.v','-v b.v','top.sv']


def test_late_ordinary_definition_can_replace_resolved_library_provider(tmp_path):
    fixture(tmp_path)
    (tmp_path/'late.sv').write_text(UDP+'module late; endmodule\n')
    lines=cli(tmp_path,'-t','late')
    assert lines[:2]==['-v a.v','-v b.v'] and set(lines[2:])=={'late.sv','top.sv'}


def test_two_ordinary_definitions_do_not_hide_behind_library(tmp_path):
    fixture(tmp_path)
    (tmp_path/'top.sv').write_text('module top; endmodule\n'+UDP)
    (tmp_path/'late.sv').write_text('module late; endmodule\n'+UDP)
    assert 'Duplicate definition' in cli(tmp_path,'-t','late',expected=1).stderr


def test_nested_library_paths_with_spaces_rebase_and_deduplicate(tmp_path):
    fixture(tmp_path)
    (tmp_path/'a.v').unlink()
    (tmp_path/'b.v').unlink()
    directory=tmp_path/'models space';directory.mkdir()
    (directory/'a one.v').write_text(UDP)
    (directory/'b two.v').write_text(UDP)
    (directory/'nested.f').write_text('-v "a one.v"\n-v "b two.v"\n-v "a one.v"\n')
    (tmp_path/'pre.f').write_text('-f "models space/nested.f"\n')
    assert cli(tmp_path)==['-v "models space/a one.v"','-v "models space/b two.v"','top.sv']
    lines=cli(tmp_path,'--path-style','absolute')
    assert lines[:2]==['-v "'+str(directory/'a one.v')+'"','-v "'+str(directory/'b two.v')+'"']


def test_same_file_with_conflicting_roles_fails_without_rewriting(tmp_path):
    fixture(tmp_path)
    (tmp_path/'pre.f').write_text('-v a.v\na.v\n')
    (tmp_path/'out.f').write_text('old\n')
    assert 'Conflicting source/library roles' in cli(tmp_path,expected=1).stderr
    assert (tmp_path/'out.f').read_text()=='old\n'


def test_missing_library_and_transitive_dependency_still_fail(tmp_path):
    fixture(tmp_path)
    (tmp_path/'out.f').write_text('old\n');(tmp_path/'b.v').unlink()
    cli(tmp_path,expected=1)
    assert (tmp_path/'out.f').read_text()=='old\n'
    (tmp_path/'b.v').write_text(UDP+'module wrapper; missing_child u(); endmodule\n')
    assert 'missing_child' in cli(tmp_path,expected=1).stderr


def test_duplicate_packages_in_libraries_remain_strict(tmp_path):
    fixture(tmp_path,'package p; endpackage\n')
    assert 'Duplicate definition' in cli(tmp_path,expected=1).stderr


def test_library_dependency_is_collected_without_plain_library_lines(tmp_path):
    fixture(tmp_path,UDP+'module wrapper; child u(); endmodule\n')
    (tmp_path/'child.sv').write_text('module child; endmodule\n')
    lines=cli(tmp_path)
    assert lines.count('-v a.v')==lines.count('-v b.v')==1
    assert 'child.sv' in lines and 'a.v' not in lines and 'b.v' not in lines


def test_inactive_definitions_do_not_satisfy_library_reference(tmp_path):
    fixture(tmp_path,'`ifdef UNSET\n'+UDP+'`endif\n')
    assert 'shared_udp' in cli(tmp_path,expected=1).stderr


def test_warm_cache_reclassifies_an_old_plain_source_hint(tmp_path):
    fixture(tmp_path)
    (tmp_path/'pre.f').write_text('')
    (tmp_path/'b.v').write_text('module other; endmodule\n')
    cli(tmp_path,'--save',tmp_path/'cache.db')
    (tmp_path/'b.v').write_text(UDP);(tmp_path/'pre.f').write_text('-v a.v\n-v b.v\n')
    assert cli(tmp_path,'--save',tmp_path/'cache.db')==['-v a.v','-v b.v','top.sv']


@pytest.mark.parametrize('reverse',[False,True])
def test_both_library_files_have_required_unique_exports_and_keep_order(tmp_path,reverse):
    fixture(tmp_path)
    (tmp_path/'a.v').write_text(UDP+'module only_a; endmodule\n')
    (tmp_path/'b.v').write_text(UDP+'module only_b; endmodule\n')
    (tmp_path/'top.sv').write_text('module top; wire q,a; shared_udp u(q,a); only_a x(); only_b y(); endmodule\n')
    order=['b.v','a.v'] if reverse else ['a.v','b.v']
    (tmp_path/'pre.f').write_text(''.join('-v '+name+'\n' for name in order))
    for _ in range(2):
        assert cli(tmp_path,'--save',tmp_path/'cache.db')==['-v '+name for name in order]+['top.sv']


def test_library_macro_and_include_follow_prelude_input_state(tmp_path):
    fixture(tmp_path)
    (tmp_path/'enabled.svh').write_text('`define ACTIVE\n')
    (tmp_path/'a.v').write_text('`include "enabled.svh"\n'+UDP)
    (tmp_path/'b.v').write_text('`ifdef ACTIVE\n'+UDP+'`else\nmodule wrapper; missing_child u(); endmodule\n`endif\n')
    assert cli(tmp_path)==['-v a.v','-v b.v','top.sv']


def test_library_role_does_not_exclude_file_from_include_lookup(tmp_path):
    directory=tmp_path/'models';directory.mkdir()
    (directory/'shared.v').write_text('`define WIDTH 8\n')
    (tmp_path/'pre.f').write_text('-v models/shared.v\n')
    (tmp_path/'top.sv').write_text('`include "shared.v"\nmodule top; localparam W=`WIDTH; endmodule\n')
    lines=cli(tmp_path)
    assert lines[0]=='-v models/shared.v' and lines[-1]=='top.sv'
    assert 'models/shared.v' not in lines
