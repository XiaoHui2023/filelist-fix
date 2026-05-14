from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from api.events.filelist_build import (
    OnBuildTopologyReadyAPI,
    OnClosureEmptyAPI,
    OnFilelistWriteAPI,
    OnModuleIndexInconsistentAPI,
    OnModuleResolveMissAPI,
    OnPreludeLoadedAPI,
    OnSessionEndAPI,
    OnSourceParsedAPI,
)
from api.events.progress import OnProgressAPI
from core.archive_sqlite import FileParseArchive
from core.bin_resolve import ToolBinaryLocator, normalize_search_roots
from core.filelist_paths import format_listed_path
from core.dep_order import prerequisite_edges, topo_prereq_first
from core.fd_search import FdModuleSearch
from core.filelist_prelude import PreludeOutcome, load_prelude_files
from core.rg_search import RgModuleSearch
from core.source_flatten import extract_dependencies_from_file
from runtime.log_format import lines_block


def _fire_closure_progress(
    ctx: Any,
    closure_done: int,
    q: deque[str],
    message: str | None,
    *,
    in_flight: bool,
) -> None:
    """更新闭包队列进度：``in_flight`` 表示当前正处理刚从队列取出的一项。"""
    if in_flight:
        total = max(1, closure_done + 1 + len(q))
    else:
        total = max(1, closure_done + len(q))
    ctx.fire(
        OnProgressAPI,
        phase="",
        current=min(closure_done, total),
        total=total,
        message=message,
    )


@dataclass
class FilelistSessionState:
    """一次构建中维护模块到文件的映射、每文件引用表与已解析集合。"""

    module_to_file: dict[str, Path] = field(default_factory=dict)
    file_refs: dict[Path, list[str]] = field(default_factory=dict)
    parsed_files: set[Path] = field(default_factory=set)
    defines: dict[str, str] = field(default_factory=dict)
    incdirs: list[Path] = field(default_factory=list)
    unresolved_modules: list[str] = field(default_factory=list)
    _unresolved_seen: set[str] = field(default_factory=set, init=False, repr=False, compare=False)

    def note_unresolved(self, name: str) -> None:
        """Record a module whose definition file was not found (ordered, deduplicated)."""
        if name not in self._unresolved_seen:
            self._unresolved_seen.add(name)
            self.unresolved_modules.append(name)


@dataclass
class ResolvedBuild:
    head_lines: list[str]
    ordered_paths: list[Path]
    state: FilelistSessionState


class ModuleResolveTools:
    """封装 fd/rg 的模块定位策略，便于注入与替换。"""

    def __init__(
        self,
        fd_exe: str,
        rg_exe: str,
        *,
        excludes: list[Path] | None = None,
    ) -> None:
        self._fd = FdModuleSearch(fd_exe)
        self._rg = RgModuleSearch(rg_exe)
        self._excludes = excludes or []

    def find_file(self, module: str, roots: list[Path]) -> Path | None:
        hit = self._fd.search(module, roots, self._excludes)
        if hit is not None:
            return hit
        return self._rg.search(module, roots, self._excludes)


class FilelistApplication:
    """编排一次构建：发事件、调核心算法；副作用由 impl 侧 sink 处理。"""

    def __init__(
        self,
        *,
        search_roots: list[Path],
        top_modules: list[str],
        prelude_paths: list[Path],
        output_path: Path,
        save_path: Path | None,
        path_style: Literal["relative", "absolute"] = "relative",
        exclude_paths: list[Path] | None = None,
        ctx: Any,
    ) -> None:
        loc = ToolBinaryLocator()
        self._search_roots = normalize_search_roots(search_roots)
        self._exclude_paths = normalize_search_roots(list(exclude_paths or []))
        self._tops = [t.strip() for t in top_modules if t.strip()]
        self._prelude_paths = prelude_paths
        self._output = output_path
        self._path_absolute = path_style == "absolute"
        self._ctx = ctx
        self._save = FileParseArchive(save_path) if save_path else FileParseArchive(None)
        self._tools = ModuleResolveTools(
            loc.resolve_fd(),
            loc.resolve_rg(),
            excludes=self._exclude_paths,
        )

    def _emit_filelist_file(self, ctx: Any, rb: ResolvedBuild) -> None:
        ctx.fire(
            OnProgressAPI,
            phase="",
            current=0,
            total=1,
            message=f"write · {self._output.name}",
        )
        lines = [h.rstrip("\n") for h in rb.head_lines]
        lines.extend(
            format_listed_path(p, self._output, absolute=self._path_absolute)
            for p in rb.ordered_paths
        )
        text = "\n".join(lines) + "\n"
        ctx.fire(OnFilelistWriteAPI, output_path=self._output, text=text)

    def _ingest_cache(self, hit: Path) -> tuple[list[str], list[str], list[str]]:
        c = self._save.get_valid(hit)
        if not c:
            return [], [], []
        defs = json.loads(c.defined_modules)
        refs = json.loads(c.referenced_modules)
        incs = json.loads(c.raw_includes)
        return defs, refs, incs

    def run(self) -> ResolvedBuild:
        """收集依赖闭包、排序并发事件；写出 filelist 与解析复用释放由 impl 消费。"""
        ctx = self._ctx
        ctx.save = self._save
        try:
            return self._run_orchestration(ctx)
        finally:
            ctx.fire(OnSessionEndAPI)

    def _run_orchestration(self, ctx: Any) -> ResolvedBuild:
        pre = load_prelude_files(self._prelude_paths) if self._prelude_paths else PreludeOutcome()
        ctx.fire(
            OnPreludeLoadedAPI,
            prelude_path_count=len(self._prelude_paths),
            define_count=len(pre.defines),
            incdir_count=len(pre.incdirs),
        )
        st = FilelistSessionState()
        st.defines.update(pre.defines)
        st.incdirs.extend(pre.incdirs)

        log = getattr(ctx, "logger", None)
        if log is not None and log.isEnabledFor(logging.DEBUG):
            log.debug(
                "prelude loaded\n%s\n%s\n%s",
                lines_block("paths", [str(p) for p in self._prelude_paths]),
                lines_block("define_keys", sorted(st.defines.keys())),
                lines_block("incdirs", [str(p) for p in st.incdirs]),
            )

        q: deque[str] = deque(self._tops)
        closure_done = 0

        _fire_closure_progress(
            ctx,
            closure_done,
            q,
            f"closure · {len(self._tops)} top(s)",
            in_flight=False,
        )

        while q:
            mod = q.popleft()
            try:
                _fire_closure_progress(
                    ctx,
                    closure_done,
                    q,
                    f"locate · {mod}",
                    in_flight=True,
                )

                if mod in st.module_to_file:
                    fp = st.module_to_file[mod]
                    if fp.resolve() not in st.parsed_files:
                        ctx.fire(OnModuleIndexInconsistentAPI, module_name=mod)
                        if log is not None and log.isEnabledFor(logging.DEBUG):
                            log.debug(
                                "skip module %r: mapped to %s but file not in parsed set",
                                mod,
                                fp,
                            )
                    else:
                        if log is not None and log.isEnabledFor(logging.DEBUG):
                            log.debug("skip module %r: already resolved via %s", mod, fp)
                    continue

                if log is not None and log.isEnabledFor(logging.DEBUG):
                    log.debug("search definition for module %r", mod)

                hit = self._tools.find_file(mod, self._search_roots)
                if hit is None:
                    st.note_unresolved(mod)
                    ctx.fire(OnModuleResolveMissAPI, module_name=mod)
                    if log is not None and log.isEnabledFor(logging.DEBUG):
                        log.debug(
                            "module %r not found under search roots (subtree from this instance skipped)",
                            mod,
                        )
                    continue
                hit = hit.resolve()
                if log is not None and log.isEnabledFor(logging.DEBUG):
                    log.debug("module %r -> %s", mod, hit)

                if hit in st.parsed_files:
                    defs, _, _ = self._ingest_cache(hit)
                    if not defs:
                        defs, _, _ = extract_dependencies_from_file(
                            hit, st.incdirs, st.defines, ctx=ctx
                        )
                    if log is not None and log.isEnabledFor(logging.DEBUG):
                        log.debug(
                            "reuse parsed file %s for module %r\n%s",
                            hit,
                            mod,
                            lines_block("defined", defs),
                        )
                    for d in defs:
                        st.module_to_file.setdefault(d, hit)
                    continue

                _fire_closure_progress(
                    ctx,
                    closure_done,
                    q,
                    f"parse · {hit.name}",
                    in_flight=True,
                )
                cached = self._save.get_valid(hit)
                cache_hit = bool(cached)
                if cached:
                    defs = json.loads(cached.defined_modules)
                    refs = json.loads(cached.referenced_modules)
                    incs = json.loads(cached.raw_includes)
                else:
                    if log is not None and log.isEnabledFor(logging.DEBUG):
                        log.debug("extract dependencies from %s", hit)
                    defs, refs, incs = extract_dependencies_from_file(
                        hit, st.incdirs, st.defines, ctx=ctx
                    )
                    self._save.put(hit, defs, refs, incs)

                if log is not None and log.isEnabledFor(logging.DEBUG):
                    log.debug(
                        "parsed %s (cache=%s)\n%s\n%s\n%s",
                        hit,
                        cache_hit,
                        lines_block("defined", defs),
                        lines_block("referenced", refs),
                        lines_block("includes", incs),
                    )

                ctx.fire(
                    OnSourceParsedAPI,
                    path=hit,
                    cache_hit=cache_hit,
                    defined_count=len(defs),
                    referenced_count=len(refs),
                )

                for d in defs:
                    st.module_to_file.setdefault(d, hit)
                st.file_refs[hit] = list(refs)
                st.parsed_files.add(hit)
                for r in refs:
                    if r not in st.module_to_file:
                        q.append(r)
                        if log is not None and log.isEnabledFor(logging.DEBUG):
                            log.debug("queue module %r (referenced from %s)", r, hit)

            finally:
                closure_done += 1
                if not q:
                    _fire_closure_progress(
                        ctx,
                        closure_done,
                        q,
                        "closure · done",
                        in_flight=False,
                    )

        if not st.file_refs:
            ctx.fire(OnClosureEmptyAPI)
            rb = ResolvedBuild(head_lines=list(pre.head_lines), ordered_paths=[], state=st)
            self._emit_filelist_file(ctx, rb)
            ctx.fire(OnProgressAPI, phase="", current=1, total=1, message="done")
            return rb

        premap = prerequisite_edges(st.file_refs, st.module_to_file)
        nodes = set(st.file_refs.keys()) | {x for ss in premap.values() for x in ss}
        ordered = topo_prereq_first(premap, nodes)
        rb = ResolvedBuild(head_lines=list(pre.head_lines), ordered_paths=ordered, state=st)

        ctx.fire(
            OnBuildTopologyReadyAPI,
            ordered_file_count=len(rb.ordered_paths),
            head_line_count=len(rb.head_lines),
        )

        self._emit_filelist_file(ctx, rb)

        ctx.fire(OnProgressAPI, phase="", current=1, total=1, message="done")
        return rb
