"""Classify model candidates and compact only safe directory-search inputs."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from collections import Counter

from api.resolve.verilog_text import InspectLibrarySourceAPI
from api.events.progress import OnProgressAPI
from core.filelist_paths import format_listed_path
from core.path_exclude import path_is_excluded


@dataclass(frozen=True)
class LibrarySourceProfile:
    definitions: tuple[str, ...]
    directory_safe: bool
    reason: str
    compiler_context: bool
    library_features: tuple[str, ...]


class LibraryDirectoryPlan:
    def __init__(self, ctx, pre, *, tops, excludes, output, absolute):
        self.ctx, self.pre = ctx, pre
        self.tops, self.excludes = set(tops), excludes
        self.output, self.absolute = output, absolute
        self.pinned = {entry.path.resolve() for entry in pre.entries if entry.kind == 'source'}
        self.directories = {path.resolve() for path in pre.library_dirs}
        self.profiles = {}

    def profile(self, path):
        key = path.resolve()
        if key not in self.profiles:
            self.ctx.fire(OnProgressAPI,
                          phase='', current=0, total=None, message=f'library · {path.name}')
            text = path.read_text(encoding='utf-8', errors='replace')
            result = self.ctx.fire(InspectLibrarySourceAPI, source_text=text)
            self.profiles[key] = LibrarySourceProfile(tuple(result.definitions),
                                                      result.directory_safe, result.reason, result.compiler_context,
                                                      tuple(result.library_features))
        return self.profiles[key]

    def _eligible(self, path):
        profile = self.profile(path)
        return (profile.directory_safe and profile.definitions == (path.stem,)
                and not self.tops.intersection(profile.definitions))

    def compact(self, rows, state):
        """Rows retain paths so output rewriting never guesses filenames from text."""
        # Source roles belong to closure; promotion is an output-only operation.
        # In particular, ordinary duplicate definitions must still fail upstream.
        sources = list(dict.fromkeys(path for _, path in rows if path is not None))
        compiler_context = any(self.profile(path).compiler_context for path in sources)
        classified = {path for path in sources if path.resolve() in state.library_sources
                      or self.profile(path).library_features}
        candidates = []
        retained = {}
        for line, path in rows:
            if path is None:
                continue
            key = path.resolve()
            if path not in classified:
                retained[path] = 'no library model features'
            elif key in self.pinned or self.tops.intersection(self.profile(path).definitions):
                retained[path] = 'explicit source or top'
            elif not self._eligible(path):
                retained[path] = self.profile(path).reason or 'unit filename mismatch'
            elif compiler_context:
                retained[path] = 'shared compilation context'
            else:
                candidates.append(path)
        candidate_set = set(candidates)
        suffixes = list(self.pre.library_extensions) if self.pre.library_dirs or self.pre._libext_explicit else []
        for path in candidates:
            if path.suffix not in suffixes and not self.pre.library_dirs:
                suffixes.append(path.suffix)
        directories = list(dict.fromkeys(path.parent for path in candidates if path.suffix in suffixes))
        rejected = {}
        # Unreferenced neighbours are not parsed by -y. Exclusions still describe
        # a user-selected boundary and cannot be re-exposed by a directory option.
        for directory in directories:
            if directory.resolve() in self.directories:
                continue
            for neighbor in directory.iterdir():
                if not neighbor.is_file() or neighbor.suffix not in suffixes:
                    continue
                if path_is_excluded(neighbor, self.excludes):
                    rejected[directory] = 'excluded neighbour: ' + neighbor.name
                    break
        # Reject a rewrite that changes a binding already established by closure.
        while True:
            active = [directory for directory in directories if directory not in rejected]
            search = list(dict.fromkeys([*self.pre.library_dirs, *active]))
            newly_rejected = {}
            for name, selected in state.module_to_file.items():
                if selected not in candidate_set and selected.resolve() not in state.library_sources:
                    continue  # Retained ordinary definitions precede lazy libraries.
                found = next((directory / (name + ext) for directory in search for ext in suffixes
                              if (directory / (name + ext)).is_file()), None)
                if found is not None and found.resolve() != selected.resolve():
                    if selected.parent in active:
                        newly_rejected[selected.parent] = 'binding conflict: ' + name
                    if found.parent in active:
                        newly_rejected[found.parent] = 'binding conflict: ' + name
            if not newly_rejected.keys() - rejected.keys():
                break
            rejected.update(newly_rejected)
        emitted = set(self.directories)
        result = []
        compacted = 0
        reasons = Counter()
        for line, path in rows:
            if line.startswith('+libext+'):
                continue
            if path is None:
                result.append(line)
                continue
            directory = path.parent
            if (path in candidate_set and directory not in rejected and path.suffix in suffixes):
                if directory.resolve() not in emitted:
                    listed = format_listed_path(directory, self.output, absolute=self.absolute)
                    result.append('-y ' + ('"' + listed + '"' if any(c.isspace() for c in listed) else listed))
                    emitted.add(directory.resolve())
                compacted += 1
            else:
                listed = format_listed_path(path, self.output, absolute=self.absolute)
                if path.resolve() in state.library_sources:
                    result.append('-v ' + ('"' + listed + '"' if any(c.isspace() for c in listed) else listed))
                else:
                    result.append(line)
                reason = retained.get(path) or rejected.get(directory) or 'configured library extensions'
                reasons[reason] += 1
                self.ctx.logger.info('library retain source=%s reason=%s features=%s',
                                     path, reason, self.profile(path).library_features)
        if suffixes and (compacted or self.pre.library_dirs or self.pre._libext_explicit):
            result.insert(0, '+libext+' + '+'.join(suffixes if compacted else self.pre.library_extensions))
        self.ctx.logger.info('library compaction checked_files=%d recognized_files=%d eligible_files=%d compacted_files=%d '
                             'directories=%d rejected_directories=%d retained_reasons=%s',
                             len(sources), len(classified), len(candidates), compacted, len(emitted), len(rejected), dict(reasons))
        return result
