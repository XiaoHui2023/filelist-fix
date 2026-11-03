from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from core.hdl_extensions import rg_include_globs
from core.path_exclude import path_is_excluded
from core.path_logical import logical_abs
from core.search_process import run_search


def _text(value: dict[str, str]) -> str:
    return value['text'] if 'text' in value else base64.b64decode(value['bytes']).decode('utf-8', errors='replace')


class RgModuleSearch:
    """Locate known names in bounded batches; parsing remains the caller's job."""

    def __init__(self, rg_exe: str) -> None:
        self._rg = rg_exe
        self._results: dict[tuple[str, tuple[Path, ...], tuple[Path, ...]], list[Path]] = {}

    def _pattern(self, module_name: str) -> str:
        return rf"\b(?:module|macromodule|primitive|package)\s+(?:(?:automatic|static)\s+)?{re.escape(module_name)}\b"

    def has_result(self, name: str, roots: list[Path], excludes: list[Path] | None = None) -> bool:
        return (name, tuple(roots), tuple(excludes or [])) in self._results

    def search_many(self, names: list[str], roots: list[Path], excludes: list[Path] | None = None) -> None:
        scope = (tuple(roots), tuple(excludes or []))
        pending = list(dict.fromkeys(name for name in names if (name, *scope) not in self._results))
        batches: list[list[str]] = []
        batch: list[str] = []
        width = 0
        for name in pending:
            added = len(self._pattern(name).encode('utf-16-le')) // 2 + 8
            if batch and (len(batch) >= 64 or width + added > 8000):
                batches.append(batch)
                batch, width = [], 0
            batch.append(name)
            width += added
        if batch:
            batches.append(batch)
        for batch in batches:
            patterns = {name: self._pattern(name) for name in batch}
            patterns = {name: (pat if any(c.isupper() for c in pat) else '(?i:' + pat + ')')
                        for name, pat in patterns.items()}
            compiled = {name: re.compile(pat) for name, pat in patterns.items()}
            hits: dict[str, dict[Path, Path]] = {name: {} for name in batch}
            for root in roots:
                command = [self._rg, '--json', '--case-sensitive', '-e', '|'.join(patterns.values())]
                for glob in rg_include_globs():
                    command.extend(['--glob', glob])
                command.append(str(root))
                result = run_search(command)
                for line in result.stdout.splitlines():
                    event = json.loads(line)
                    if event['type'] != 'match':
                        continue
                    data = event['data']
                    path = logical_abs(Path(_text(data['path'])))
                    if path_is_excluded(path, excludes or []):
                        continue
                    text = _text(data['lines'])
                    for name, pattern in compiled.items():
                        if pattern.search(text):
                            hits[name].setdefault(path.resolve(), path)
            for name in batch:
                self._results[name, *scope] = sorted(hits[name].values(), key=lambda p: (len(p.parts), str(p)))

    def search_all(self, module_name: str, roots: list[Path], excludes: list[Path] | None = None) -> list[Path]:
        self.search_many([module_name], roots, excludes)
        return self._results[module_name, tuple(roots), tuple(excludes or [])]

    def search(self, module_name: str, roots: list[Path], excludes: list[Path] | None = None) -> Path | None:
        hits = self.search_all(module_name, roots, excludes)
        return hits[0] if len(hits) == 1 else None
