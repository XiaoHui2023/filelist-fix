from __future__ import annotations

import json
import logging
from collections import deque
from itertools import islice
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from api.events.filelist_build import (
    OnBuildTopologyReadyAPI,
    OnBuildOrderInvalidAPI,
    OnClosureEmptyAPI,
    OnFilelistWriteAPI,
    OnModuleIndexInconsistentAPI,
    OnModuleResolveDuplicateAPI,
    OnModuleResolveMissAPI,
    OnPreludeLoadedAPI,
    OnSessionEndAPI,
    OnSourceParsedAPI,
)
from api.events.progress import OnProgressAPI
from core.archive_sqlite import FileParseArchive
from core.bin_resolve import ToolBinaryLocator, normalize_search_roots
from core.dep_order import (add_macro_prerequisites, add_macro_state_prerequisites, prerequisite_edges, topo_prereq_first,
                            schedule_prelude_dependencies, validate_macro_schedule, prioritize_macro_order)
from core.fd_search import FdModuleSearch
from core.hdl_extensions import HD_SOURCE_EXTENSIONS
from core.library_directories import LibraryDirectoryPlan
from core.filelist_paths import format_incdir_line, format_source_line
from core.filelist_prelude import PreludeOutcome, load_prelude_files_with_signature
from core.path_logical import logical_abs
from core.path_exclude import PathExclusions, path_is_excluded
from core.rg_search import RgModuleSearch
from core.search_process import SearchFailure
from core.source_flatten import extract_dependencies_from_file
from core.parse_monitor import note_cache_timing
from time import perf_counter
from verilog_text.parse_budget import ParseTimeout
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
    library_providers: dict[str, list[Path]] = field(default_factory=dict)
    library_sources: set[Path] = field(default_factory=set)
    file_refs: dict[Path, list[str]] = field(default_factory=dict)
    file_symbols: dict[Path, dict[str, list[str]]] = field(default_factory=dict)
    scope_resolution_dirty: bool = False
    satisfied_type_scopes: set[str] = field(default_factory=set)
    macro_origins: dict[str, Path | None] = field(default_factory=dict)
    file_macro_bindings: dict[Path, dict[str, Path | None]] = field(default_factory=dict)
    macro_input_timeline: list[Path | tuple[str, str]] = field(default_factory=list)
    parsed_resolved: set[Path] = field(default_factory=set)
    defines: dict[str, str] = field(default_factory=dict)
    incdirs: list[Path] = field(default_factory=list)
    incdir_lines_before: dict[Path, list[str]] = field(default_factory=dict)
    unresolved_modules: list[str] = field(default_factory=list)
    _unresolved_seen: set[str] = field(default_factory=set, init=False, repr=False, compare=False)
    _logical_by_resolved: dict[Path, Path] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def canonical_source_path(self, hit: Path) -> Path:
        """同一 inode 多次以不同逻辑路径出现时，统一为首次见到的逻辑路径。"""
        h = logical_abs(hit)
        r = h.resolve()
        if r not in self._logical_by_resolved:
            self._logical_by_resolved[r] = h
        return self._logical_by_resolved[r]

    def inode_was_parsed(self, hit: Path) -> bool:
        """是否已对该 inode 做过依赖抽取（与写出 filelist 用的逻辑路径无关）。"""
        return logical_abs(hit).resolve() in self.parsed_resolved

    def note_inode_parsed(self, hit: Path) -> None:
        self.parsed_resolved.add(logical_abs(hit).resolve())

    def note_symbols(self, path: Path, symbols: dict[str, list[str]]) -> None:
        self.macro_input_timeline.append(path)
        self.file_symbols[path] = symbols
        self.file_macro_bindings[path] = {name: self.macro_origins[name]
                                          for name in symbols.get('macro_uses', []) if name in self.macro_origins}
        for event in symbols.get('macro_events', []):
            action, _, name = event.partition(' ')
            if action == 'define':
                self.macro_origins[name] = path
            elif action == 'undef':
                self.macro_origins.pop(name, None)
            elif action == 'clear':
                self.macro_origins.clear()
        for event in symbols.get('macro_value_events', []):
            action, _, payload = event.partition(' ')
            name, _, value = payload.partition('=')
            if action == 'define':
                self.defines[name] = value
            elif action == 'undef':
                self.defines.pop(name, None)
            elif action == 'clear':
                self.defines.clear()
        if symbols.get('declared_types') or symbols.get('package_imports'):
            self.scope_resolution_dirty = True

    def note_unresolved(self, name: str) -> None:
        """未找到定义时记录一次；并将该名记入 ``_unresolved_seen``，本会话内不再 fd/rg、不再入队。"""
        if name not in self._unresolved_seen:
            self._unresolved_seen.add(name)
            self.unresolved_modules.append(name)


@dataclass
class ResolvedBuild:
    head_lines: list[str]
    ordered_paths: list[Path]
    state: FilelistSessionState
    prelude_sources: dict[int, Path] = field(default_factory=dict)
    prelude_dependencies: dict[int, list[Path]] = field(default_factory=dict)


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
        self._excludes = PathExclusions(excludes or [])
        self._module_excludes = self._excludes
        self.pending_names: list[str] = []

    def reset(self, *, library_sources: list[Path] | None = None) -> None:
        self._fd._indexes.clear()
        self._rg._results.clear()
        self.pending_names.clear()
        self._module_excludes = PathExclusions([*self._excludes, *(library_sources or [])])

    def find_all(self, module: str, roots: list[Path]) -> list[Path]:
        excludes = self._module_excludes
        fd_hits = self._fd.search_all(module, roots, excludes)
        if len(fd_hits) > 1:
            return fd_hits
        if len(fd_hits) == 1:
            return fd_hits
        if not self._rg.has_result(module, roots, excludes):
            pending = [module, *self.pending_names]
            pending = list(dict.fromkeys(name for name in pending
                                       if not self._fd.search_all(name, roots, excludes)))
            self._rg.search_many(pending, roots, excludes)
        return self._rg.search_all(module, roots, excludes)

    def fd_search_by_filename(
        self,
        filename: str,
        roots: list[Path],
        excludes: list[Path] | None = None,
    ) -> list[Path]:
        return self._fd.search_by_filename(filename, roots, excludes or self._excludes)

    def find_file(self, module: str, roots: list[Path]) -> Path | None:
        hits = self.find_all(module, roots)
        if len(hits) == 1:
            return hits[0]
        return None


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
        library_directories: bool = False,
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
        self._save_path = save_path
        self._library_dirs: list[Path] = []
        self._library_extensions: list[str] = []
        self._compact_libraries = library_directories
        self._library_plan = None
        self._tools = ModuleResolveTools(
            loc.resolve_fd(),
            loc.resolve_rg(),
            excludes=self._exclude_paths,
        )

    def _locate_module_file(self, mod: str) -> Path | None:
        """先查 ``--save`` 的模块路径提示；可信则省略 fd/rg，否则退回检索。

        提示路径上磁盘文件仍在但单文件缓存已过期时，按库内旧解析行的定义名与引用名清除 ``module_path``，便于下级模块重新定位；仍沿用该路径并交由后续步骤重新解析。
        """
        hint = self._save.get_module_hint(mod)
        if hint is not None:
            hp = logical_abs(hint)
            source_allowed = False
            for root in self._search_roots:
                resolved = hp.resolve()
                anchor = root.resolve()
                if resolved == anchor:
                    hp, source_allowed = root, True
                    break
                if root.is_dir() and resolved.is_relative_to(anchor) and hp.suffix.lstrip('.').lower() in HD_SOURCE_EXTENSIONS:
                    hp, source_allowed = root / resolved.relative_to(anchor), True
                    break
            # Library candidates are cheap exact-name probes. Recheck them so new
            # duplicates, exclusions and extension changes cannot hide behind hints.
            if (not hp.is_file() or path_is_excluded(hp, self._exclude_paths) or not source_allowed
                    or hp.resolve() in self._ctx.session_state.library_sources
                    or (self._library_plan is not None and
                        hp.parent.resolve() in self._library_plan.directories)):
                self._save.delete_module_hint(mod)
            else:
                rec = self._save.get_valid(hp)
                if rec is not None:
                    defs_chk = json.loads(rec.defined_modules)
                    if mod in defs_chk:
                        log = getattr(self._ctx, 'logger', None)
                        if log is not None:
                            log.info('locate kind=hint module=%s source=%s', mod, hp)
                        return hp
                    self._save.delete_module_hint(mod)
                else:
                    self._save.invalidate_module_hints_for_stale_file(hp)
                    return hp
        hits = self._tools.find_all(mod, self._search_roots)
        if not hits:
            providers = self._ctx.session_state.library_providers.get(mod, [])
            if providers:
                return providers[0]
        if not hits:
            hits = list(dict.fromkeys(
                logical_abs(directory / (mod + ext))
                for directory in self._library_dirs for ext in self._library_extensions
                if (directory / (mod + ext)).is_file()
                and not path_is_excluded(directory / (mod + ext), self._exclude_paths)
            ))
            if self._compact_libraries and hits:
                selected = hits[0]
                self._ctx.session_state.library_sources.add(selected.resolve())
                return selected
        if len(hits) > 1:
            ctx = self._ctx
            ctx.fire(
                OnModuleResolveDuplicateAPI,
                module_name=mod,
                candidate_paths=hits,
            )
            return None
        if len(hits) == 1:
            return logical_abs(hits[0])
        return None

    def _register_defined_modules(
        self,
        ctx: Any,
        st: FilelistSessionState,
        hit: Path,
        defs: list[str],
        *, library: bool = False, packages: tuple[str, ...] | list[str] = (),
    ) -> bool:
        """登记普通定义与有序库候选；普通定义和包的冲突返回 False。"""
        names = list(dict.fromkeys(defs))
        if library:
            for name in names:
                if name not in packages:
                    st.library_providers.setdefault(name, []).append(hit)
            names = [name for name in names if name in packages]
        for name in names:
            prev = st.module_to_file.get(name)
            if (prev is not None and prev.resolve() != hit.resolve()
                    and prev not in st.library_providers.get(name, [])):
                ctx.fire(
                    OnModuleResolveDuplicateAPI,
                    module_name=name,
                    candidate_paths=[prev, hit],
                )
                return False
        for name in names:
            st.module_to_file[name] = hit
        return True

    @staticmethod
    def _discard_imported_type_refs(st: FilelistSessionState) -> None:
        """Resolve scope-only names through the packages imported by that file."""
        if not st.scope_resolution_dirty:
            return
        st.scope_resolution_dirty = False
        for path, refs in st.file_refs.items():
            symbols = st.file_symbols.get(path, {})
            imported_types: set[str] = set()
            for package in symbols.get('package_imports', []):
                package_path = st.module_to_file.get(package)
                imported_types.update(st.file_symbols.get(package_path, {}).get('declared_types', []))
            removable = (imported_types & set(symbols.get('scope_references', []))) - set(symbols.get('instance_modules', []))
            st.satisfied_type_scopes.update(removable)
            st.file_refs[path] = [name for name in refs if name not in removable]

    def _emit_filelist_file(self, ctx: Any, rb: ResolvedBuild) -> None:
        ctx.fire(
            OnProgressAPI,
            phase="",
            current=0,
            total=1,
            message=f"write · {self._output.name}",
        )
        rows: list[tuple[str, Path | None]] = []
        def append_source(path: Path) -> None:
            rows.extend((line, None) for line in rb.state.incdir_lines_before.get(path, ()))
            rows.append((format_source_line(path, self._output, absolute=self._path_absolute), path))

        for index, h in enumerate(rb.head_lines):
            for dependency in rb.prelude_dependencies.get(index, ()):
                append_source(dependency)
            source = rb.prelude_sources.get(index)
            if source is not None:
                rows.extend((line, None) for line in rb.state.incdir_lines_before.get(source, ()))
            rows.append((h.rstrip("\n"), source))
        for p in rb.ordered_paths:
            append_source(p)
        lines = self._library_plan.compact(rows, rb.state) if self._library_plan is not None else [line for line, _ in rows]
        text = "\n".join(lines) + "\n"
        ctx.fire(OnFilelistWriteAPI, output_path=self._output, text=text)

    def _restore_discovered_incdirs(
        self, st: FilelistSessionState, host: Path, directories: list[Path],
    ) -> None:
        """Replay directory state and format it for this run's output location."""
        for directory in directories:
            if directory not in st.incdirs:
                st.incdirs.append(directory)
            line = format_incdir_line(directory, self._output, absolute=self._path_absolute)
            lines = st.incdir_lines_before.setdefault(host, [])
            if line not in lines:
                lines.append(line)

    def run(self) -> ResolvedBuild | None:
        """收集依赖闭包、排序并发事件；写出 filelist 与解析复用释放由 impl 消费。"""
        ctx = self._ctx
        try:
            return self._run_orchestration(ctx)
        except (ParseTimeout, SearchFailure) as exc:
            ctx.logger.error("%s; previous filelist preserved", exc)
            ctx.console.print(f"{exc}; previous filelist preserved", markup=False,
                              highlight=False, soft_wrap=True)
            ctx.request_exit(2)
            return None
        finally:
            ctx.fire(OnSessionEndAPI)

    def _run_orchestration(self, ctx: Any) -> ResolvedBuild | None:
        if self._prelude_paths:
            pre, _ = load_prelude_files_with_signature(
                self._prelude_paths,
                output_path=self._output,
                path_absolute=self._path_absolute,
            )
        else:
            pre = PreludeOutcome()
        self._library_dirs = pre.library_dirs
        self._library_extensions = pre.library_extensions
        st = FilelistSessionState()
        self._library_plan = (LibraryDirectoryPlan(ctx, pre, tops=self._tops, excludes=self._exclude_paths,
                                                  output=self._output, absolute=self._path_absolute)
                              if self._compact_libraries else None)
        st.library_sources = {entry.path.resolve() for entry in pre.entries if entry.kind == 'library'}
        library_files = [entry.path for entry in pre.entries if entry.kind == 'library']
        if self._compact_libraries:
            library_files.extend(path for directory in pre.library_dirs for path in directory.iterdir()
                                 if path.is_file() and path.suffix in pre.library_extensions)
        self._tools.reset(library_sources=library_files)
        ctx.search_roots = list(dict.fromkeys([*self._search_roots, *self._library_dirs]))
        ctx.exclude_paths = self._exclude_paths
        ctx.session_state = st
        ctx.output_path = self._output
        ctx.path_absolute = self._path_absolute
        ctx.module_resolve_tools = self._tools
        prelude_sources: dict[int, Path] = {}
        prelude_refs: list[str] = []
        for entry in pre.entries:
            if entry.kind == "define":
                st.defines[entry.name] = entry.value
                st.macro_origins[entry.name] = None
                st.macro_input_timeline.append(('define', entry.name))
            elif entry.kind == "incdir":
                st.incdirs.append(entry.path)
            else:
                hit = st.canonical_source_path(entry.path)
                ctx.fire(OnProgressAPI, phase='', current=0, total=None,
                         message=f'parse · {hit.name}')
                before_incdirs = list(st.incdirs)
                symbols: dict[str, list[str]] = {}
                defs, refs, _ = extract_dependencies_from_file(
                    hit, st.incdirs, st.defines, ctx=ctx, output_defines=st.defines, output_symbols=symbols,
                )
                if getattr(ctx, "exit_code", None):
                    return None
                self._restore_discovered_incdirs(
                    st, hit, [p for p in st.incdirs if p not in before_incdirs],
                )
                is_library = entry.kind == 'library'
                if is_library:
                    st.library_sources.add(hit.resolve())
                if not self._register_defined_modules(ctx, st, hit, defs,
                                                     library=is_library,
                                                     packages=symbols.get('package_definitions', [])):
                    return None
                st.file_refs[hit] = list(refs)
                st.note_symbols(hit, symbols)
                st.note_inode_parsed(hit)
                prelude_sources[entry.line_index] = hit
                prelude_refs.extend(refs)
                ctx.fire(OnSourceParsedAPI, path=hit, cache_hit=False,
                         defined_count=len(defs), referenced_count=len(refs))
        self._save = FileParseArchive(
            self._save_path,
            defines=st.defines,
            incdirs=st.incdirs,
        )
        ctx.save = self._save
        ctx.fire(
            OnPreludeLoadedAPI,
            prelude_path_count=len(self._prelude_paths),
            define_count=len(st.defines),
            incdir_count=len(st.incdirs),
        )
        log = getattr(ctx, "logger", None)
        if log is not None and log.isEnabledFor(logging.DEBUG):
            log.debug(
                "prelude loaded\n%s\n%s\n%s",
                lines_block("paths", [str(p) for p in self._prelude_paths]),
                lines_block("define_keys", sorted(st.defines.keys())),
                lines_block("incdirs", [str(p) for p in st.incdirs]),
            )

        q: deque[str] = deque([*self._tops, *prelude_refs])
        closure_done = 0

        _fire_closure_progress(
            ctx,
            closure_done,
            q,
            f"closure · {len(self._tops)} top(s)",
            in_flight=False,
        )

        while q:
            if getattr(ctx, "exit_code", None):
                break
            mod = q.popleft()
            try:
                self._discard_imported_type_refs(st)
                if mod in st.satisfied_type_scopes and mod not in self._tops and not any(mod in refs for refs in st.file_refs.values()):
                    continue
                _fire_closure_progress(
                    ctx,
                    closure_done,
                    q,
                    f"locate · {mod}",
                    in_flight=True,
                )

                if mod in st.module_to_file:
                    fp = st.module_to_file[mod]
                    if fp.resolve() not in st.parsed_resolved:
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

                if mod in st._unresolved_seen:
                    if log is not None and log.isEnabledFor(logging.DEBUG):
                        log.debug("skip module %r: fd/rg already missed this session", mod)
                    continue

                if log is not None and log.isEnabledFor(logging.DEBUG):
                    log.debug("search definition for module %r", mod)

                self._save.set_context(st.defines, st.incdirs)
                self._tools.pending_names = [name for name in islice(q, 63)
                                             if name not in st.module_to_file and name not in st._unresolved_seen]
                hit = self._locate_module_file(mod)
                if getattr(ctx, "exit_code", None):
                    break
                if hit is None:
                    st.note_unresolved(mod)
                    ctx.fire(OnModuleResolveMissAPI, module_name=mod)
                    if log is not None and log.isEnabledFor(logging.DEBUG):
                        log.debug(
                            "module %r not found under search roots (subtree from this instance skipped)",
                            mod,
                        )
                    continue
                hit = st.canonical_source_path(hit)
                if log is not None and log.isEnabledFor(logging.DEBUG):
                    log.debug("module %r -> %s", mod, hit)

                if st.inode_was_parsed(hit):
                    if hit in st.library_providers.get(mod, []):
                        st.module_to_file[mod] = hit
                        continue
                    st.note_unresolved(mod)
                    ctx.fire(OnModuleResolveMissAPI, module_name=mod)
                    continue

                _fire_closure_progress(
                    ctx,
                    closure_done,
                    q,
                    f"parse · {hit.name}",
                    in_flight=True,
                )
                cache_started = perf_counter()
                self._save.set_context(st.defines, st.incdirs)
                cached = self._save.get_valid(hit)
                cache_hit = bool(cached)
                if cached:
                    defs = json.loads(cached.defined_modules)
                    refs = json.loads(cached.referenced_modules)
                    incs = json.loads(cached.raw_includes)
                    symbols = json.loads(cached.symbols_json)
                    self._restore_discovered_incdirs(
                        st, hit, [Path(p) for p in json.loads(cached.discovered_incdirs_json)],
                    )
                    note_cache_timing(ctx, hit, perf_counter() - cache_started)
                else:
                    if log is not None and log.isEnabledFor(logging.DEBUG):
                        log.debug("extract dependencies from %s", hit)
                    dependencies: list[Path] = []
                    symbols = {}
                    before_incdirs = list(st.incdirs)
                    defs, refs, incs = extract_dependencies_from_file(
                        hit, st.incdirs, st.defines, ctx=ctx, dependency_files=dependencies, output_symbols=symbols,
                    )
                    if getattr(ctx, "exit_code", None):
                        break
                    discovered = [p for p in st.incdirs if p not in before_incdirs]
                    self._restore_discovered_incdirs(st, hit, discovered)
                    self._save.put(hit, defs, refs, incs, dependency_files=dependencies,
                                   discovered_incdirs=discovered, symbols=symbols)

                if getattr(ctx, "exit_code", None):
                    break

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

                is_library = hit.resolve() in st.library_sources
                if is_library:
                    for name in defs:
                        self._save.delete_module_hint(name)
                else:
                    self._save.upsert_module_hints(hit, defs, [])
                if not self._register_defined_modules(ctx, st, hit, defs, library=is_library,
                                                     packages=symbols.get('package_definitions', [])):
                    break
                if is_library and mod in defs:
                    st.module_to_file[mod] = hit
                st.file_refs[hit] = list(refs)
                st.note_symbols(hit, symbols)
                st.note_inode_parsed(hit)
                if mod not in defs:
                    st.note_unresolved(mod)
                    ctx.fire(OnModuleResolveMissAPI, module_name=mod)
                for r in reversed(refs):
                    if r not in st.module_to_file and r not in st._unresolved_seen:
                        q.appendleft(r)
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

        if getattr(ctx, "exit_code", None):
            return None
        if st.unresolved_modules:
            ctx.request_exit(1)
            return None

        if not st.file_refs:
            ctx.fire(OnClosureEmptyAPI)
            rb = ResolvedBuild(head_lines=list(pre.head_lines), ordered_paths=[], state=st)
            self._emit_filelist_file(ctx, rb)
            ctx.fire(OnProgressAPI, phase="", current=1, total=1, message="done")
            return rb

        # Library options are retained providers, not ordinary module-order edges.
        # Packages still require their normal declaration-before-use ordering.
        ordered_definitions = {name: path for name, path in st.module_to_file.items()
                               if path.resolve() not in st.library_sources
                               or name in st.file_symbols.get(path, {}).get('package_definitions', [])}
        premap = prerequisite_edges(st.file_refs, ordered_definitions)
        macro_constraints: set[str] = set()
        try:
            topo_prereq_first(premap, premap)
            macro_edges: set[tuple[Path, Path]] = set()
            macro_constraints = add_macro_prerequisites(premap, st.file_symbols, st.file_macro_bindings, macro_edges)
            macro_constraints.update(add_macro_state_prerequisites(
                premap, st.file_symbols, st.file_macro_bindings, st.macro_input_timeline, macro_edges,
            ))
            prioritize_macro_order(premap, st.file_symbols, macro_edges, prelude_sources)
            nodes = set(st.file_refs.keys()) | {x for ss in premap.values() for x in ss}
            before, ordered = schedule_prelude_dependencies(
                premap, topo_prereq_first(premap, nodes), prelude_sources,
            )
            defines_at = {entry.line_index: entry.name for entry in pre.entries if entry.kind == 'define'}
            timeline: list[Path | tuple[str, str]] = []
            for index in range(len(pre.head_lines)):
                timeline.extend(before.get(index, []))
                if index in defines_at:
                    timeline.append(('define', defines_at[index]))
                if index in prelude_sources:
                    timeline.append(prelude_sources[index])
            timeline.extend(ordered)
            validate_macro_schedule(st.file_symbols, timeline)
        except ValueError as error:
            prefix = f'Macro order constraints {sorted(macro_constraints)}: ' if macro_constraints else ''
            ctx.fire(OnBuildOrderInvalidAPI, message=prefix + str(error))
            return None
        rb = ResolvedBuild(head_lines=list(pre.head_lines), ordered_paths=ordered, state=st,
                           prelude_sources=prelude_sources, prelude_dependencies=before)

        ctx.fire(
            OnBuildTopologyReadyAPI,
            ordered_file_count=len(rb.ordered_paths),
            head_line_count=len(rb.head_lines),
        )

        self._emit_filelist_file(ctx, rb)

        ctx.fire(OnProgressAPI, phase="", current=1, total=1, message="done")
        return rb
