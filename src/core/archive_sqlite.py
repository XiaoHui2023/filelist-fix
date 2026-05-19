from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core.bin_resolve import path_stat_sig
from core.parse_context import (
    defines_signature,
    incdirs_json,
    parse_context_compatible,
)


@dataclass
class CachedFileRecord:
    path: str
    mtime_ns: int
    size: int
    defined_modules: str
    referenced_modules: str
    raw_includes: str
    defines_sig: str
    incdirs_json: str


_ARCHIVE_SCHEMA_VERSION = "2"


class FileParseArchive:
    """在指定路径用 SQLite 保存单文件解析产物（定义/引用/include），用 mtime+size 判定是否仍可与当前源文件对齐。

    另存 ``module_path``：模块名到定义文件路径的上次解析结果；命中且源未变时可省略 fd/rg。某源文件缓存失效时，按该文件在库中的旧 ``defined``/``referenced`` 集合清除相关模块提示，便于下级模块重新定位。

    解析环境按 ``+define+`` 摘要与 ``+incdir+`` 路径集合校验：仅追加 incdir 时仍可复用旧行；宏变化或缩小 incdir 集合则失效。
    """

    def __init__(
        self,
        db_path: Path | None,
        *,
        defines: dict[str, str] | None = None,
        incdirs: list[Path] | None = None,
    ) -> None:
        self._path = db_path
        self._defines = dict(defines or {})
        self._incdirs = list(incdirs or [])
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
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS module_path (
                    module TEXT PRIMARY KEY,
                    path TEXT NOT NULL
                )
                """
            )
            self._conn.commit()
            self._migrate_schema()
            self._ensure_archive_schema_meta()

    def _migrate_schema(self) -> None:
        if self._conn is None:
            return
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(file_cache)").fetchall()
        }
        if "defines_sig" not in cols:
            self._conn.execute(
                "ALTER TABLE file_cache ADD COLUMN defines_sig TEXT NOT NULL DEFAULT ''"
            )
        if "incdirs_json" not in cols:
            self._conn.execute(
                "ALTER TABLE file_cache ADD COLUMN incdirs_json TEXT NOT NULL DEFAULT '[]'"
            )
        self._conn.commit()

    def _ensure_archive_schema_meta(self) -> None:
        if self._conn is None:
            return
        row = self._conn.execute(
            "SELECT value FROM archive_meta WHERE key = ?",
            ("archive_schema",),
        ).fetchone()
        if row is None:
            legacy = self._conn.execute(
                "SELECT value FROM archive_meta WHERE key = ?",
                ("prelude_signature",),
            ).fetchone()
            if legacy is not None:
                self._conn.execute("DELETE FROM archive_meta WHERE key = ?", ("prelude_signature",))
            self._conn.execute(
                "INSERT INTO archive_meta(key, value) VALUES(?, ?)",
                ("archive_schema", _ARCHIVE_SCHEMA_VERSION),
            )
            self._conn.commit()
            return
        if row[0] != _ARCHIVE_SCHEMA_VERSION:
            self._conn.execute(
                "UPDATE archive_meta SET value = ? WHERE key = ?",
                (_ARCHIVE_SCHEMA_VERSION, "archive_schema"),
            )
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _row_to_record(self, row: tuple[object, ...]) -> CachedFileRecord:
        return CachedFileRecord(
            path=str(row[0]),
            mtime_ns=int(row[1]),
            size=int(row[2]),
            defined_modules=str(row[3]),
            referenced_modules=str(row[4]),
            raw_includes=str(row[5]),
            defines_sig=str(row[6]) if len(row) > 6 else "",
            incdirs_json=str(row[7]) if len(row) > 7 else "[]",
        )

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
        rec = self._row_to_record(row)
        if not parse_context_compatible(
            rec.defines_sig,
            rec.incdirs_json,
            defines=self._defines,
            incdirs=self._incdirs,
        ):
            return None
        return rec

    def fetch_file_cache_row(self, path: Path) -> CachedFileRecord | None:
        """返回 ``path`` 在库中的缓存行（不校验磁盘 mtime/size，可能已过期）。"""
        if self._conn is None:
            return None
        key = str(path.resolve())
        row = self._conn.execute("SELECT * FROM file_cache WHERE path = ?", (key,)).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def invalidate_module_hints_for_stale_file(self, path: Path) -> None:
        """按 ``path`` 在库中**旧**解析行的 ``defined`` ∪ ``referenced`` 删除 ``module_path`` 行。"""
        if self._conn is None:
            return
        rec = self.fetch_file_cache_row(path)
        if rec is None:
            return
        defs = json.loads(rec.defined_modules)
        refs = json.loads(rec.referenced_modules)
        names = sorted(set(defs) | set(refs))
        if not names:
            return
        qmarks = ",".join("?" * len(names))
        self._conn.execute(f"DELETE FROM module_path WHERE module IN ({qmarks})", names)
        self._conn.commit()

    def get_module_hint(self, module: str) -> Path | None:
        """返回上次记录的模块定义路径；无记录或未启用库时为 ``None``。"""
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT path FROM module_path WHERE module = ?",
            (module,),
        ).fetchone()
        if row is None:
            return None
        return Path(row[0])

    def delete_module_hint(self, module: str) -> None:
        if self._conn is None:
            return
        self._conn.execute("DELETE FROM module_path WHERE module = ?", (module,))
        self._conn.commit()

    def upsert_module_hints(self, path: Path, defined_modules: list[str], also_modules: list[str]) -> None:
        """把 ``defined_modules`` 与 ``also_modules`` 中的名字映射到 ``path``（覆盖同模块旧路径）。"""
        if self._conn is None:
            return
        key = str(path.resolve())
        names = sorted(set(defined_modules) | set(also_modules))
        for n in names:
            self._conn.execute(
                """
                INSERT INTO module_path(module, path) VALUES(?, ?)
                ON CONFLICT(module) DO UPDATE SET path = excluded.path
                """,
                (n, key),
            )
        self._conn.commit()

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
        d_sig = defines_signature(self._defines)
        inc_json = incdirs_json(self._incdirs)

        self._conn.execute(
            """
            INSERT INTO file_cache(
                path,mtime_ns,size,defined_modules,referenced_modules,raw_includes,
                defines_sig,incdirs_json
            )
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
              mtime_ns=excluded.mtime_ns,
              size=excluded.size,
              defined_modules=excluded.defined_modules,
              referenced_modules=excluded.referenced_modules,
              raw_includes=excluded.raw_includes,
              defines_sig=excluded.defines_sig,
              incdirs_json=excluded.incdirs_json
            """,
            (
                key,
                mtime_ns,
                size,
                json.dumps(defined),
                json.dumps(referenced),
                json.dumps(includes),
                d_sig,
                inc_json,
            ),
        )
        self._conn.commit()
