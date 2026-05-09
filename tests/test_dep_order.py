from pathlib import Path

from core.dep_order import prerequisite_edges, topo_prereq_first


def test_topo_dependency_before_user(tmp_path: Path) -> None:
    a = tmp_path / "a.v"
    b = tmp_path / "b.v"
    a.write_text("", encoding="utf-8")
    b.write_text("", encoding="utf-8")
    refs = {a: ["mB"], b: []}
    modmap = {"mA": a, "mB": b}
    pre = prerequisite_edges(refs, modmap)
    nodes = set(refs.keys()) | {b}
    order = topo_prereq_first(pre, nodes)
    ar, br = a.resolve(), b.resolve()
    assert order.index(br) < order.index(ar)
