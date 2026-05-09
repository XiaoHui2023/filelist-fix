from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core.bin_resolve import path_stat_sig


@dataclass
class CachedFileRecord:
    path: str
    mtime_ns: int
    size: int
    defined_modules: str
    referenced_modules: str
    raw_includes: str


class FileParseArchive:
    """SQLite 缓存：按路径记住解析过的模块集合与依赖，用 mtime+size 做失效判断。"""

    def __init__(self, db_path: Path | None) -> None:
        self._path = db_path
        self._conn: sqlite3.Connection | None = None
        if db_path is not None:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(db_path))
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_cache (
                    path TEXT PRIMARY KEY,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    defined_modules TEXT NOT NULL,
                    referenced_modules TEXT NOT NULL,
                    raw_includes TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def get_valid(self, path: Path) -> CachedFileRecord | None:
        if self._conn is None:
            return None
        key = str(path.resolve())
        row = self._conn.execute("SELECT * FROM file_cache WHERE path = ?", (key,)).fetchone()
        if row is None:
            return None
        mtime_ns, size = path_stat_sig(path)
        if row[1] != mtime_ns or row[2] != size:
            return None
        return CachedFileRecord(
            path=row[0],
            mtime_ns=row[1],
            size=row[2],
            defined_modules=row[3],
            referenced_modules=row[4],
            raw_includes=row[5],
        )

    def put(
        self,
        path: Path,
        defined: list[str],
        referenced: list[str],
        includes: list[str],
    ) -> None:
        if self._conn is None:
            return
        mtime_ns, size = path_stat_sig(path)
        key = str(path.resolve())

        self._conn.execute(
            """
            INSERT INTO file_cache(path,mtime_ns,size,defined_modules,referenced_modules,raw_includes)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
              mtime_ns=excluded.mtime_ns,
              size=excluded.size,
              defined_modules=excluded.defined_modules,
              referenced_modules=excluded.referenced_modules,
              raw_includes=excluded.raw_includes
            """,
            (
                key,
                mtime_ns,
                size,
                json.dumps(defined),
                json.dumps(referenced),
                json.dumps(includes),
            ),
        )
        self._conn.commit()
