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
    """在指定路径用 SQLite 保存单文件解析产物（定义/引用/include），用 mtime+size 判定是否仍可与当前源文件对齐。

    ``prelude_signature`` 变化时整表失效，避免 prelude 宏/``+incdir+`` 变更后仍误用旧缓存。
    """

    def __init__(self, db_path: Path | None, *, prelude_signature: str = "") -> None:
        self._path = db_path
        self._prelude_signature = prelude_signature
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
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archive_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            self._conn.commit()
            self._ensure_prelude_meta()

    def _ensure_prelude_meta(self) -> None:
        if self._conn is None:
            return
        row = self._conn.execute(
            "SELECT value FROM archive_meta WHERE key = ?",
            ("prelude_signature",),
        ).fetchone()
        if row is None:
            self._conn.execute("DELETE FROM file_cache")
            self._conn.execute(
                "INSERT INTO archive_meta(key, value) VALUES(?, ?)",
                ("prelude_signature", self._prelude_signature),
            )
            self._conn.commit()
            return
        if row[0] != self._prelude_signature:
            self._conn.execute("DELETE FROM file_cache")
            self._conn.execute(
                "UPDATE archive_meta SET value = ? WHERE key = ?",
                (self._prelude_signature, "prelude_signature"),
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
