"""黄金 RTL 中注释用例与 core 去注释逻辑对齐的回归。"""

from pathlib import Path

from core.source_flatten import extract_dependencies_from_file
from runtime.context import AppContext


def test_comment_farm_example_resolves_expected_deps(app_ctx: AppContext) -> None:
    root = Path(__file__).resolve().parents[1]
    rtl = root / "example" / "complex_rtl"
    farm = rtl / "torture" / "torture_comment_farm.v"
    incs = [rtl, rtl / "common", rtl / "hier", rtl / "pieces"]
    defs, refs, _ = extract_dependencies_from_file(farm, incs, {}, ctx=app_ctx)
    assert defs == ["torture_comment_farm"]
    assert set(refs) == {"torture_dep_a", "torture_dep_b"}
