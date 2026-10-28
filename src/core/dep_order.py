from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from core.path_logical import logical_abs


def prerequisite_edges(
    file_to_refs: dict[Path, list[str]],
    module_to_file: dict[str, Path],
) -> dict[Path, set[Path]]:
    """若文件 A 引用了模块 M 且 M 定义于 B，则 B 是 A 的前置依赖文件。"""
    pre: dict[Path, set[Path]] = {}
    for fp in file_to_refs:
        pre.setdefault(logical_abs(fp), set())
    for fp, refs in file_to_refs.items():
        fr = logical_abs(fp)
        for r in refs:
            bf = module_to_file.get(r)
            if bf is None:
                continue
            br = logical_abs(bf)
            if br == fr:
                continue
            pre.setdefault(fr, set()).add(br)
    return pre


def topo_prereq_first(prereq: dict[Path, set[Path]], seeds: Iterable[Path]) -> list[Path]:
    """对给定子图做深度后序：依赖文件先于引用者出现；输入为全部参与排序的节点。"""
    nodes = list({logical_abs(p) for p in seeds})
    seen: set[Path] = set()
    visiting: set[Path] = set()
    out: list[Path] = []

    def dfs(n: Path) -> None:
        r = logical_abs(n)
        if r in seen:
            return
        if r in visiting:
            raise ValueError(f"Cyclic source dependency at {r}")
        visiting.add(r)
        for d in sorted(prereq.get(r, ()), key=lambda p: str(p)):
            dfs(d)
        visiting.remove(r)
        seen.add(r)
        out.append(r)

    for s in sorted(nodes, key=lambda p: str(p)):
        dfs(s)
    return out


def schedule_prelude_dependencies(
    prereq: dict[Path, set[Path]], ordered: list[Path], sources: dict[int, Path],
) -> tuple[dict[int, list[Path]], list[Path]]:
    """Insert discovered prerequisites before fixed prelude sources without moving directives."""
    pinned = set(sources.values())
    emitted: set[Path] = set()
    visiting: set[Path] = set()
    before: dict[int, list[Path]] = {}

    def visit(path: Path, bucket: list[Path], current: Path) -> None:
        if path in emitted:
            return
        if path in visiting:
            raise ValueError(f"Cyclic source dependency at {path}")
        if path in pinned and path != current:
            raise ValueError(f"Prelude source {current} requires later prelude source {path}")
        visiting.add(path)
        for dependency in sorted(prereq.get(path, ()), key=str):
            visit(dependency, bucket, current)
        visiting.remove(path)
        emitted.add(path)
        if path != current:
            bucket.append(path)

    for index, path in sources.items():
        bucket: list[Path] = []
        visit(path, bucket, path)
        before[index] = bucket
    return before, [p for p in ordered if p not in emitted]
