from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api.events.progress import OnProgressAPI
from core.archive_sqlite import FileParseArchive
from core.bin_resolve import ToolBinaryLocator, normalize_search_roots
from core.dep_order import prerequisite_edges, topo_prereq_first
from core.fd_search import FdModuleSearch
from core.filelist_prelude import PreludeOutcome, load_prelude_files
from core.rg_search import RgModuleSearch
from core.source_flatten import extract_dependencies_from_file


@dataclass
class FilelistSessionState:
    """一次构建中维护模块到文件的映射、每文件引用表与已解析集合。"""

    module_to_file: dict[str, Path] = field(default_factory=dict)
    file_refs: dict[Path, list[str]] = field(default_factory=dict)
    parsed_files: set[Path] = field(default_factory=set)
    defines: dict[str, str] = field(default_factory=dict)
    incdirs: list[Path] = field(default_factory=list)


@dataclass
class ResolvedBuild:
    head_lines: list[str]
    ordered_paths: list[Path]
    state: FilelistSessionState


class ModuleResolveTools:
    """封装 fd/rg 的模块定位策略，便于注入与替换。"""

    def __init__(self, fd_exe: str, rg_exe: str) -> None:
        self._fd = FdModuleSearch(fd_exe)
        self._rg = RgModuleSearch(rg_exe)

    def find_file(self, module: str, roots: list[Path]) -> Path | None:
        hit = self._fd.search(module, roots)
        if hit is not None:
            return hit
        return self._rg.search(module, roots)


class FilelistApplication:
    """CLI 门面：串联前导 filelist、搜索、解析、排序与写出。"""

    def __init__(
        self,
        *,
        search_roots: list[Path],
        top_modules: list[str],
        prelude_paths: list[Path],
        output_path: Path | None,
        archive_path: Path | None,
        rg_path: Path | None,
        fd_path: Path | None,
        ctx: Any,
        repo_root: Path | None = None,
    ) -> None:
        loc = ToolBinaryLocator(repo_root)
        self._search_roots = normalize_search_roots(search_roots)
        self._tops = [t.strip() for t in top_modules if t.strip()]
        self._prelude_paths = prelude_paths
        self._output = output_path
        self._ctx = ctx
        self._archive = FileParseArchive(archive_path) if archive_path else FileParseArchive(None)
        self._tools = ModuleResolveTools(loc.resolve_fd(fd_path), loc.resolve_rg(rg_path))
        self._logger = getattr(ctx, "logger", None) or logging.getLogger(__name__)

    def _ingest_cache(self, hit: Path) -> tuple[list[str], list[str], list[str]]:
        c = self._archive.get_valid(hit)
        if not c:
            return [], [], []
        defs = json.loads(c.defined_modules)
        refs = json.loads(c.referenced_modules)
        incs = json.loads(c.raw_includes)
        return defs, refs, incs

    def run(self) -> ResolvedBuild:
        """收集依赖闭包、排序并可选写出 filelist。"""
        ctx = self._ctx
        pre = load_prelude_files(self._prelude_paths) if self._prelude_paths else PreludeOutcome()
        st = FilelistSessionState()
        st.defines.update(pre.defines)
        st.incdirs.extend(pre.incdirs)

        q: deque[str] = deque(self._tops)
        done = 0
        ctx.fire(
            OnProgressAPI,
            phase="解析与闭包收集",
            current=done,
            total=None,
            message="队列已就绪",
        )

        while q:
            mod = q.popleft()
            if mod in st.module_to_file:
                fp = st.module_to_file[mod]
                if fp.resolve() not in st.parsed_files:
                    self._logger.warning("内部状态不一致，跳过模块 %s", mod)
                continue

            hit = self._tools.find_file(mod, self._search_roots)
            if hit is None:
                self._logger.warning("未定位到模块 %s，跳过", mod)
                continue
            hit = hit.resolve()

            if hit in st.parsed_files:
                defs, _, _ = self._ingest_cache(hit)
                if not defs:
                    defs, _, _ = extract_dependencies_from_file(hit, st.incdirs, st.defines)
                for d in defs:
                    st.module_to_file.setdefault(d, hit)
                continue

            cached = self._archive.get_valid(hit)
            if cached:
                defs = json.loads(cached.defined_modules)
                refs = json.loads(cached.referenced_modules)
                incs = json.loads(cached.raw_includes)
            else:
                defs, refs, incs = extract_dependencies_from_file(hit, st.incdirs, st.defines)
                self._archive.put(hit, defs, refs, incs)

            for d in defs:
                st.module_to_file.setdefault(d, hit)
            st.file_refs[hit] = list(refs)
            st.parsed_files.add(hit)
            for r in refs:
                if r not in st.module_to_file:
                    q.append(r)

            done += 1
            ctx.fire(
                OnProgressAPI,
                phase="解析与闭包收集",
                current=done,
                total=None,
                message=hit.name,
            )

        if not st.file_refs:
            self._archive.close()
            return ResolvedBuild(head_lines=list(pre.head_lines), ordered_paths=[], state=st)

        premap = prerequisite_edges(st.file_refs, st.module_to_file)
        nodes = set(st.file_refs.keys()) | {x for ss in premap.values() for x in ss}
        ordered = topo_prereq_first(premap, nodes)
        rb = ResolvedBuild(head_lines=list(pre.head_lines), ordered_paths=ordered, state=st)

        if self._output is not None:
            ctx.fire(OnProgressAPI, phase="写出 filelist", current=0, total=1, message=str(self._output))
            lines = [h.rstrip("\n") for h in rb.head_lines]
            lines.extend(str(p) for p in rb.ordered_paths)
            self._output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._archive.close()
        ctx.fire(OnProgressAPI, phase="完成", current=1, total=1, message=None)
        return rb
