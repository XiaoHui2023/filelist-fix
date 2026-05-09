from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def prerequisite_edges(
    file_to_refs: dict[Path, list[str]],
    module_to_file: dict[str, Path],
) -> dict[Path, set[Path]]:
    """若文件 A 引用了模块 M 且 M 定义于 B，则 B 是 A 的前置依赖文件。"""
    pre: dict[Path, set[Path]] = {}
    for fp in file_to_refs:
        pre.setdefault(fp.resolve(), set())
    for fp, refs in file_to_refs.items():
        fr = fp.resolve()
        for r in refs:
            bf = module_to_file.get(r)
            if bf is None:
                continue
            br = bf.resolve()
            if br == fr:
                continue
            pre.setdefault(fr, set()).add(br)
    return pre


def topo_prereq_first(prereq: dict[Path, set[Path]], seeds: Iterable[Path]) -> list[Path]:
    """对给定子图做深度后序：依赖文件先于引用者出现；输入为全部参与排序的节点。"""
    nodes = list({p.resolve() for p in seeds})
    seen: set[Path] = set()
    out: list[Path] = []

    def dfs(n: Path) -> None:
        r = n.resolve()
        if r in seen:
            return
        seen.add(r)
        for d in sorted(prereq.get(r, ()), key=lambda p: str(p)):
            dfs(d)
        out.append(r)

    for s in sorted(nodes, key=lambda p: str(p)):
        dfs(s)
    return out
