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


def add_macro_prerequisites(
    prereq: dict[Path, set[Path]],
    symbols: dict[Path, dict[str, list[str]]],
    bindings: dict[Path, dict[str, Path | None]],
    macro_edges: set[tuple[Path, Path]] | None = None,
) -> set[str]:
    """Merge file macro provenance into the same graph as module/package edges."""
    providers: dict[str, set[Path]] = {}
    for path, info in symbols.items():
        for name in info.get('macro_exports', []):
            providers.setdefault(name, set()).add(path)
    constrained: set[str] = set()
    for path, info in symbols.items():
        known = bindings.get(path, {})
        for name in info.get('macro_uses', []):
            if name in known:
                donor = known[name]
            else:
                candidates = providers.get(name, set()) - {path}
                if len(candidates) > 1:
                    raise ValueError(f'Macro {name} has ambiguous source providers for {path}: {sorted(map(str, candidates))}')
                donor = next(iter(candidates), None)
            if donor is not None and donor != path:
                prereq.setdefault(path, set()).add(donor)
                if macro_edges is not None:
                    macro_edges.add((path, donor))
                constrained.add(name)
    return constrained


def prioritize_macro_order(
    prereq: dict[Path, set[Path]], symbols: dict[Path, dict[str, list[str]]],
    macro_edges: set[tuple[Path, Path]], sources: dict[int, Path],
) -> None:
    """Relax module ordering only on a macro-induced cycle; package/pin edges stay hard."""
    if not macro_edges:
        return
    hard = set(macro_edges)
    for path, info in symbols.items():
        for dependency in prereq.get(path, set()):
            if set(info.get('package_imports', []) + info.get('scope_references', [])) & set(symbols.get(dependency, {}).get('package_definitions', [])):
                hard.add((path, dependency))
    pinned = list(sources.values())
    for previous, following in zip(pinned, pinned[1:]):
        prereq.setdefault(following, set()).add(previous)
        hard.add((following, previous))

    def cycle() -> list[tuple[Path, Path]]:
        visited: set[Path] = set()
        active: list[Path] = []
        positions: dict[Path, int] = {}
        def visit(node: Path) -> list[tuple[Path, Path]]:
            if node in positions:
                ring = active[positions[node]:] + [node]
                return list(zip(ring, ring[1:]))
            if node in visited:
                return []
            positions[node] = len(active)
            active.append(node)
            for dep in sorted(prereq.get(node, set()), key=str):
                found = visit(dep)
                if found:
                    return found
            active.pop()
            positions.pop(node)
            visited.add(node)
            return []
        for node in sorted(prereq, key=str):
            found = visit(node)
            if found:
                return found
        return []

    while True:
        ring = cycle()
        if not ring:
            return
        removable = [edge for edge in ring if edge not in hard]
        if not set(ring) & macro_edges or not removable:
            raise ValueError(f'Cyclic source ordering constraints: {ring}')
        source, dependency = sorted(removable, key=lambda edge: tuple(map(str, edge)))[0]
        prereq[source].remove(dependency)


def validate_macro_schedule(
    symbols: dict[Path, dict[str, list[str]]],
    timeline: Iterable[Path | tuple[str, str]],
) -> None:
    """Reject emission order that changes a parsed external conditional environment."""
    defined: set[str] = set()
    items = list(timeline)
    provider_names = {event.partition(' ')[2] for info in symbols.values()
                      for event in info.get('macro_events', []) if event.startswith('define ')}
    provider_names.update(item[1] for item in items if isinstance(item, tuple))
    for item in items:
        if isinstance(item, tuple):
            defined.add(item[1])
            continue
        info = symbols.get(item, {})
        for name in info.get('macro_condition_defined', []):
            if name not in defined:
                raise ValueError(f'Macro {name} is undefined before {item}; parsed condition was defined')
        for name in info.get('macro_condition_undefined', []):
            if name in defined:
                raise ValueError(f'Macro {name} is defined before {item}; parsed condition was undefined')
        conditional = set(info.get('macro_condition_undefined', []))
        for name in set(info.get('macro_uses', [])) & provider_names - conditional:
            if name not in defined:
                raise ValueError(f'Macro {name} is unavailable before {item}')
        for event in info.get('macro_events', []):
            action, _, name = event.partition(' ')
            if action == 'define':
                defined.add(name)
            elif action == 'undef':
                defined.discard(name)
            elif action == 'clear':
                defined.clear()


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
