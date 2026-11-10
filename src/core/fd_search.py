from __future__ import annotations

import re
from pathlib import Path

from core.hdl_extensions import HD_SOURCE_EXTENSIONS
from core.path_exclude import PathExclusions, path_is_excluded
from core.path_logical import logical_abs
from core.search_process import run_search


class FdModuleSearch:
    """Share a filename inventory within one build, preserving fd traversal rules."""

    def __init__(self, fd_exe: str) -> None:
        self._fd = fd_exe
        self._indexes: dict[Path, dict[str, list[Path]]] = {}

    def _index(self, root: Path) -> dict[str, list[Path]]:
        if root not in self._indexes:
            index: dict[str, list[Path]] = {}
            if root.is_file():
                # fd searches directories. Explicit source files retain the
                # content-search fallback instead of becoming filename hits.
                paths = []
            else:
                result = run_search([self._fd, "--type", "f", "--print0", ".", str(root)])
                paths = [Path(value) for value in result.stdout.split("\0") if value]
            for path in paths:
                path = logical_abs(path)
                index.setdefault(path.name.casefold(), []).append(path)
            self._indexes[root] = index
        return self._indexes[root]

    def _collect(self, filenames: list[str], roots: list[Path], excludes: list[Path] | PathExclusions | None) -> list[Path]:
        hits: dict[Path, Path] = {}
        for root in roots:
            index = self._index(root)
            for filename in filenames:
                sensitive = any(char.isupper() for char in filename)
                for path in index.get(filename.casefold(), ()):
                    if not re.fullmatch(re.escape(filename), path.name, flags=0 if sensitive else re.IGNORECASE):
                        continue
                    if not path_is_excluded(path, excludes or []):
                        hits.setdefault(path.resolve(), path)
        return sorted(hits.values(), key=lambda p: (len(p.parts), str(p)))

    def search_all(self, module_name: str, roots: list[Path], excludes: list[Path] | PathExclusions | None = None) -> list[Path]:
        return self._collect([module_name + "." + ext for ext in HD_SOURCE_EXTENSIONS], roots, excludes)

    def search_by_filename(self, filename: str, roots: list[Path], excludes: list[Path] | PathExclusions | None = None) -> list[Path]:
        name = Path(filename).name
        return self._collect([name], roots, excludes) if name else []

    def search(self, module_name: str, roots: list[Path], excludes: list[Path] | PathExclusions | None = None) -> Path | None:
        hits = self.search_all(module_name, roots, excludes)
        return hits[0] if len(hits) == 1 else None
