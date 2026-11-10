"""Plan library roles and compact only files addressable by directory lookup."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from api.resolve.verilog_text import InspectLibrarySourceAPI
from api.events.progress import OnProgressAPI
from core.filelist_paths import format_listed_path
from core.path_exclude import path_is_excluded


@dataclass(frozen=True)
class LibrarySourceProfile:
    definitions: tuple[str, ...]
    cell_definitions: tuple[str, ...]
    directory_safe: bool
    reason: str


class LibraryDirectoryPlan:
    def __init__(self, ctx, pre, *, tops, excludes, output, absolute):
        self.ctx, self.pre = ctx, pre
        self.tops, self.excludes = set(tops), excludes
        self.output, self.absolute = output, absolute
        self.explicit = {entry.path.resolve() for entry in pre.entries if entry.kind == 'library'}
        self.directories = {path.resolve() for path in pre.library_dirs}
        self.profiles = {}

    def profile(self, path):
        key = path.resolve()
        if key not in self.profiles:
            self.ctx.fire(OnProgressAPI,
                          phase='', current=0, total=None, message=f'library · {path.name}')
            text = path.read_text(encoding='utf-8', errors='replace')
            result = self.ctx.fire(InspectLibrarySourceAPI, source_text=text)
            self.profiles[key] = LibrarySourceProfile(tuple(result.definitions), tuple(result.cell_definitions),
                                                      result.directory_safe, result.reason)
        return self.profiles[key]

    def is_cell(self, path):
        profile = self.profile(path)
        return (bool(profile.definitions) and profile.definitions == profile.cell_definitions
                and not self.tops.intersection(profile.definitions)
                and profile.reason in {'', 'multiple compilation units'})

    def _eligible(self, path):
        profile = self.profile(path)
        return (profile.directory_safe and profile.definitions == (path.stem,)
                and not self.tops.intersection(profile.definitions))

    def compact(self, rows, state):
        """Rows retain paths so output rewriting never guesses filenames from text."""
        candidates = []
        for line, path in rows:
            if path is not None and path.resolve() in state.library_sources and self._eligible(path):
                candidates.append(path)
        suffixes = list(self.pre.library_extensions) if self.pre.library_dirs else []
        for path in candidates:
            if path.suffix not in suffixes and not self.pre.library_dirs:
                suffixes.append(path.suffix)
        directories = list(dict.fromkeys(path.parent for path in candidates if path.suffix in suffixes))
        rejected = set()
        # A directory is not a curated file set: audit every newly exposed suffix.
        for directory in directories:
            if directory.resolve() in self.directories:
                continue
            for neighbor in directory.iterdir():
                if not neighbor.is_file() or neighbor.suffix not in suffixes:
                    continue
                if (path_is_excluded(neighbor, self.excludes) or not self._eligible(neighbor)
                        or (neighbor.resolve() not in self.explicit and not self.is_cell(neighbor))):
                    rejected.add(directory)
                    break
        sequence = [path.parent for path in candidates]
        for directory in directories:
            indexes = [i for i, value in enumerate(sequence) if value == directory]
            if indexes and any(value != directory for value in sequence[indexes[0]:indexes[-1] + 1]):
                rejected.add(directory)
        # Reject a rewrite that changes a binding already established by closure.
        while True:
            active = [directory for directory in directories if directory not in rejected]
            search = list(dict.fromkeys([*self.pre.library_dirs, *active]))
            newly_rejected = set()
            for name, selected in state.module_to_file.items():
                if selected.parent not in active or selected.resolve() not in state.library_sources:
                    continue
                found = next((directory / (name + ext) for directory in search for ext in suffixes
                              if (directory / (name + ext)).is_file()), None)
                if found is not None and found.resolve() != selected.resolve():
                    newly_rejected.add(selected.parent)
                    if found.parent in active:
                        newly_rejected.add(found.parent)
            if not newly_rejected - rejected:
                break
            rejected.update(newly_rejected)
        emitted = set(self.directories)
        result = []
        compacted = 0
        for line, path in rows:
            if line.startswith('+libext+'):
                continue
            if path is None or path.resolve() not in state.library_sources:
                result.append(line)
                continue
            directory = path.parent
            if (path in candidates and directory not in rejected and path.suffix in suffixes):
                if directory.resolve() not in emitted:
                    listed = format_listed_path(directory, self.output, absolute=self.absolute)
                    result.append('-y ' + ('"' + listed + '"' if any(c.isspace() for c in listed) else listed))
                    emitted.add(directory.resolve())
                compacted += 1
            else:
                listed = format_listed_path(path, self.output, absolute=self.absolute)
                result.append('-v ' + ('"' + listed + '"' if any(c.isspace() for c in listed) else listed))
                self.ctx.logger.info('library retain source=%s reason=%s', path,
                                     self.profile(path).reason or 'directory/name/order safety')
        if suffixes and (compacted or self.pre.library_dirs or self.pre._libext_explicit):
            result.insert(0, '+libext+' + '+'.join(suffixes))
        self.ctx.logger.info('library directories compacted_files=%d directories=%d', compacted, len(emitted))
        return result
