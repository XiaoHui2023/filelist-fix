from __future__ import annotations

from verilog_text.ref_index import collect_module_ref_sites, format_module_ref_index
from verilog_text.squeeze import squeeze_for_dependency_scan


def test_collect_instance_ref_site_fields() -> None:
    src = """
module top;
  leaf_mod u_leaf (.a(1));
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    sites = collect_module_ref_sites(squ)
    inst = [s for s in sites if s.referenced_module == "leaf_mod"]
    assert len(inst) == 1
    s = inst[0]
    assert s.parent_module == "top"
    assert s.instance_name == "u_leaf"
    assert s.kind == "instance"
    assert s.line_in_scan_input >= 1
    assert "leaf_mod" in s.excerpt


def test_format_module_ref_index_groups_by_referenced_name() -> None:
    from verilog_text.ref_index import ModuleRefSite

    entries = [
        (
            "/proj/a.sv",
            "by_file/a",
            ModuleRefSite(
                referenced_module="missing_mod",
                parent_module="top",
                kind="instance",
                instance_name="u0",
                line_in_scan_input=10,
                excerpt="missing_mod u0 ();",
            ),
        ),
    ]
    text = format_module_ref_index(entries)
    assert "REFERENCED: missing_mod" in text
    assert "/proj/a.sv" in text
    assert "parent:      top" in text
    assert "instance:    u0" in text
    assert "line:        10" in text
