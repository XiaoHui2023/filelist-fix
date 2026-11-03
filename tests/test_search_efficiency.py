from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def cli(work, *args, expected=0):
    log = work / 'run.log'
    command = [sys.executable, str(ROOT/'src'), '-s', str(work), '-t', 'top',
               '-o', str(work/'out.f'), '-l', str(log), *map(str, args)]
    cp = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert cp.returncode == expected, cp.stderr
    return log.read_text(encoding='utf-8'), cp


@pytest.mark.parametrize('by_content', [False, True])
def test_wide_closure_uses_one_inventory_and_bounded_content_batches(tmp_path, by_content):
    names = [f'leaf{i}' for i in range(130)]
    (tmp_path/'top.sv').write_text('module top;\n'+''.join(f'{n} u{i}();\n' for i,n in enumerate(names))+'endmodule\n')
    for name in names:
        (tmp_path/(('unit_' if by_content else '')+name+'.sv')).write_text(f'module {name}; endmodule\n')
    log, _ = cli(tmp_path, '--save', tmp_path/'cache.db')
    tool_lines = [line for line in log.splitlines() if 'locate tool=' in line]
    assert sum('fd' in line.split(' status=')[0] for line in tool_lines) == 1
    assert sum('rg' in line.split(' status=')[0] for line in tool_lines) == (3 if by_content else 0)
    output = (tmp_path/'out.f').read_text().splitlines()
    assert len(output) == 131 and len(set(output)) == 131
    assert set(output) == {'top.sv', *(('unit_' if by_content else '')+n+'.sv' for n in names)}
    warm, _ = cli(tmp_path, '--save', tmp_path/'cache.db')
    assert 'locate tool=' not in warm and 'parse total' not in warm
    assert warm.count('parse stage=cache status=ok') == 131


def test_batch_retains_all_names_on_one_line_and_individual_smart_case(tmp_path):
    (tmp_path/'top.sv').write_text('module top;\nfoo a();\nBar b();\nendmodule\n')
    (tmp_path/'units.sv').write_text('module foo; endmodule module Bar; endmodule\n')
    log, _ = cli(tmp_path)
    assert (tmp_path/'out.f').read_text().splitlines() == ['units.sv', 'top.sv']
    assert sum('locate tool=' in line and 'rg' in line.split(' status=')[0] for line in log.splitlines()) == 1


def test_fd_smart_case_and_include_inventory_are_shared(tmp_path):
    (tmp_path/'top.sv').write_text('`include "settings.h"\nmodule top;\nleaf u();\nendmodule\n')
    folder=tmp_path/'headers';folder.mkdir()
    (folder/'settings.h').write_text('`define ENABLED\n')
    (tmp_path/'LEAF.SV').write_text('module leaf; endmodule\n')
    log, _ = cli(tmp_path)
    assert sum('locate tool=' in line and 'fd' in line.split(' status=')[0] for line in log.splitlines()) == 1
    assert 'LEAF.SV' in (tmp_path/'out.f').read_text()


def test_exclusions_ignores_overlapping_roots_and_duplicates(tmp_path):
    (tmp_path/'top.sv').write_text('module top;\nleaf u();\nendmodule\n')
    (tmp_path/'leaf.sv').write_text('module leaf; endmodule\n')
    ignored=tmp_path/'ignored';ignored.mkdir();(ignored/'leaf.sv').write_text('module leaf; endmodule\n')
    (tmp_path/'.ignore').write_text('ignored/\n')
    cli(tmp_path, '-s', tmp_path)
    other=tmp_path/'other';other.mkdir();(other/'leaf.sv').write_text('module leaf; endmodule\n')
    saved=(tmp_path/'out.f').read_bytes()
    cli(tmp_path, expected=1)
    assert (tmp_path/'out.f').read_bytes() == saved
    cli(tmp_path, '-x', other)


def test_rg_batch_duplicate_and_missing_preserve_old_output(tmp_path):
    (tmp_path/'top.sv').write_text('module top;\na u();\nb v();\nendmodule\n')
    (tmp_path/'one.sv').write_text('module a; endmodule\n')
    (tmp_path/'original.sv').write_text('module b; endmodule\n')
    cli(tmp_path)
    previous=(tmp_path/'out.f').read_bytes()
    (tmp_path/'two.sv').write_text('module b; endmodule\n')
    cli(tmp_path, expected=1)
    assert (tmp_path/'out.f').read_bytes() == previous
    (tmp_path/'two.sv').unlink();(tmp_path/'original.sv').unlink()
    cli(tmp_path, expected=1)
    assert (tmp_path/'out.f').read_bytes() == previous


def test_prelude_progress_is_emitted_before_its_read(tmp_path):
    source=tmp_path/'top.sv';source.write_text('module top; endmodule\n')
    log,cp=cli(tmp_path,'-p',source)
    assert log.index('parse · top.sv') < log.index('parse stage=read')
    assert 'slow dependency extraction' not in cp.stderr


def test_warm_directory_alias_keeps_hints_and_logical_output(tmp_path):
    real=tmp_path/'real';real.mkdir()
    (real/'top.sv').write_text('module top;\nleaf u();\nendmodule\n')
    (real/'leaf.sv').write_text('module leaf; endmodule\n')
    alias=tmp_path/'alias'
    if os.name=='nt':
        cp=subprocess.run(['cmd','/c','mklink','/J',str(alias),str(real)],capture_output=True)
        assert cp.returncode==0,cp.stderr
    else:
        alias.symlink_to(real, target_is_directory=True)
    try:
        command=[sys.executable,str(ROOT/'src'),'-s',str(alias),'-t','top','-o',str(tmp_path/'out.f'),
                 '--save',str(tmp_path/'cache.db'),'-l',str(tmp_path/'alias.log')]
        for _ in range(2):
            cp=subprocess.run(command,capture_output=True,text=True,timeout=15);assert cp.returncode==0,cp.stderr
        text=(tmp_path/'alias.log').read_text(encoding='utf-8')
        assert 'locate tool=' not in text and text.count('locate kind=hint')==2
        assert (tmp_path/'out.f').read_text().splitlines()==['alias/leaf.sv','alias/top.sv']
    finally:
        os.rmdir(alias) if os.name=='nt' else alias.unlink()


def test_search_timeout_and_error_are_failures_not_misses(monkeypatch):
    from core.search_process import run_search,SearchFailure
    def timeout(*a,**kw):
        assert kw['timeout']==120
        raise subprocess.TimeoutExpired(a[0],120)
    monkeypatch.setattr(subprocess,'run',timeout)
    with pytest.raises(SearchFailure,match='definition search failed'):
        run_search(['fd','root'])
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:subprocess.CompletedProcess(a[0],2,'','denied'))
    with pytest.raises(SearchFailure,match='denied'):
        run_search(['rg','root'])


def test_rg_batches_equal_individual_queries_with_overlapping_names(tmp_path):
    from core.bin_resolve import ToolBinaryLocator
    from core.rg_search import RgModuleSearch
    executable=ToolBinaryLocator().resolve_rg()
    fixtures=['module foo$bar; endmodule', 'module FOO; endmodule',
              'package static p; endpackage', 'primitive automatic udp; endprimitive',
              '// module missing;\nmodule Foo; endmodule']
    for index,text in enumerate(fixtures):
        (tmp_path/f'unit{index}.sv').write_text(text+'\n')
    names=['foo','foo$bar','Foo','FOO','p','udp','missing','absent']
    search=RgModuleSearch(executable);search.search_many(names,[tmp_path])
    for name in names:
        cp=subprocess.run([executable,'-l','-S','-e',search._pattern(name),'--glob','*.sv',str(tmp_path)],
                          capture_output=True,text=True,encoding='utf-8',timeout=10)
        assert cp.returncode in (0,1)
        assert {p.resolve() for p in search.search_all(name,[tmp_path])} == {Path(p).resolve() for p in cp.stdout.splitlines()}


def test_deep_chain_preserves_dependency_order_and_shares_inventory(tmp_path):
    for index in range(18):
        name='top' if index==0 else f'node{index}'
        ref=f'node{index+1} u();\n' if index<17 else ''
        (tmp_path/f'unit{index}.sv').write_text(f'module {name};\n{ref}endmodule\n')
    log,_=cli(tmp_path)
    assert (tmp_path/'out.f').read_text().splitlines()==[f'unit{i}.sv' for i in reversed(range(18))]
    tools=[line for line in log.splitlines() if 'locate tool=' in line]
    assert sum('fd' in line.split(' status=')[0] for line in tools)==1
    assert sum('rg' in line.split(' status=')[0] for line in tools)==18


def test_filename_index_preserves_fd_unicode_case_matching(tmp_path):
    import re
    from core.bin_resolve import ToolBinaryLocator
    from core.fd_search import FdModuleSearch
    from core.hdl_extensions import HD_SOURCE_EXTENSIONS
    executable=ToolBinaryLocator().resolve_fd()
    for name in ['foo.v','FOO.SV','ss.v','ß.v','K.v']:
        (tmp_path/name).write_text('')
    search=FdModuleSearch(executable)
    for name in ['foo','FOO','ss','k']:
        pattern=rf"^{re.escape(name)}\.({'|'.join(HD_SOURCE_EXTENSIONS)})$"
        cp=subprocess.run([executable,'--type','f',pattern,str(tmp_path)],capture_output=True,text=True,encoding='utf-8',timeout=10)
        assert cp.returncode in (0,1)
        assert {p.resolve() for p in search.search_all(name,[tmp_path])}=={Path(p).resolve() for p in cp.stdout.splitlines()}
