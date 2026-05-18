from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.bin_resolve import path_stat_sig
from core.filelist_paths import format_listed_path
from core.hdl_extensions import HD_SOURCE_EXTENSIONS
from core.path_logical import logical_abs

_INCDIR = re.compile(r"^\+incdir\+(\"([^\"]+)\"|(\S+))")
_DEFINE = re.compile(r"^\+define\+([A-Za-z_]\w*)(?:=(.*))?$")
_COMMENT = re.compile(r"^\s*//")
_NEST_FILELIST = re.compile(r"^\s*-[fF]\s+(.+)$")
_V_LINE = re.compile(r"^\s*-v\s+(.+)$")
_Y_LINE = re.compile(r"^\s*-y\s+(.+)$")
_MAX_FILELIST_NEST = 64


def _is_hdl_source_file(path: Path) -> bool:
    suf = path.suffix.lower()
    if suf == ".vhdl":
        return True
    ext = suf[1:] if suf.startswith(".") else ""
    return ext in HD_SOURCE_EXTENSIONS


def _strip_trailing_line_comment(line: str) -> str:
    """去掉行尾 ``//`` 注释（忽略引号内的 ``//`` 的极简启发式）。"""
    in_sq = in_dq = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "/" and i + 1 < n and line[i + 1] == "/" and not in_sq and not in_dq:
            return line[:i].rstrip()
        i += 1
    return line.rstrip()


def _parse_first_path_token(rest: str) -> str:
    """``-f`` / ``-v`` / ``-y`` 等行尾参数：支持引号路径或首个空白分隔 token。"""
    s = rest.strip()
    if not s:
        return ""
    if s[0] == '"':
        end = 1
        while end < len(s):
            if s[end] == "\\":
                end = min(end + 2, len(s))
                continue
            if s[end] == '"':
                return s[1:end]
            end += 1
        return s[1:]
    if s[0] == "'":
        end = 1
        while end < len(s):
            if s[end] == "'":
                return s[1:end]
            end += 1
        return s[1:]
    parts = s.split()
    return parts[0] if parts else s


def _resolve_path_token(host_dir: Path, token: str) -> Path:
    raw = Path(token).expanduser()
    if raw.is_absolute():
        return logical_abs(raw)
    return logical_abs(host_dir / raw)


def _format_incdir_line(inc_resolved: Path, output_path: Path, *, absolute: bool) -> str:
    disp = format_listed_path(inc_resolved, output_path, absolute=absolute)
    if " " in disp or disp.startswith("+"):
        return f'+incdir+"{disp}"'
    return f"+incdir+{disp}"


def _format_define_line(key: str, value: str) -> str:
    if not value:
        return f"+define+{key}"
    return f"+define+{key}={value}"


def prelude_signature_from_files(files: list[Path]) -> str:
    """由本轮实际读过的 prelude / 嵌套 ``-f`` 文件（有序、去重首次出现）生成存档校验串。"""
    h = hashlib.sha256()
    for p in files:
        rp = str(logical_abs(Path(p)))
        try:
            mt, sz = path_stat_sig(p)
        except OSError:
            mt, sz = 0, 0
        h.update(rp.encode("utf-8", errors="replace"))
        h.update(b"\0")
        h.update(str(mt).encode("ascii"))
        h.update(b"\0")
        h.update(str(sz).encode("ascii"))
        h.update(b"\0")
    return h.hexdigest()


def _record_sig(path: Path, sig_files: list[Path], sig_seen: set[Path]) -> None:
    rp = logical_abs(path)
    if rp not in sig_seen:
        sig_seen.add(rp)
        sig_files.append(rp)


def _resolve_incdir(prelude_file: Path, inc: str) -> Path:
    """将 +incdir+ 路径解析为绝对路径；相对路径相对于**当前 filelist 文件**所在目录。"""
    raw = Path(inc).expanduser()
    if raw.is_absolute():
        return logical_abs(raw)
    return logical_abs(prelude_file.parent / raw)


@dataclass
class PreludeOutcome:
    """filelist 前导：写入输出的行（已展开、无嵌套 ``-f``）、解析用目录与宏。"""

    head_lines: list[str] = field(default_factory=list)
    incdirs: list[Path] = field(default_factory=list)
    defines: dict[str, str] = field(default_factory=dict)


def _consume_one_filelist(
    path: Path,
    *,
    output_path: Path,
    path_absolute: bool,
    outcome: PreludeOutcome,
    visited: set[Path],
    sig_files: list[Path],
    sig_seen: set[Path],
    depth: int,
) -> None:
    if depth > _MAX_FILELIST_NEST:
        raise ValueError(f"prelude 嵌套 -f 超过 {_MAX_FILELIST_NEST} 层: {path}")
    path_expanded = path.expanduser()
    path_disk = path_expanded.resolve()
    if path_disk in visited:
        return
    visited.add(path_disk)
    path_log = logical_abs(path_expanded)
    _record_sig(path_log, sig_files, sig_seen)

    text = path_log.read_text(encoding="utf-8", errors="replace")
    host_parent = path_log.parent
    for raw_line in text.splitlines():
        line = _strip_trailing_line_comment(raw_line)
        s = line.strip()
        if not s:
            continue
        if _COMMENT.match(s):
            continue

        fm = _NEST_FILELIST.match(s)
        if fm:
            tok = _parse_first_path_token(fm.group(1))
            if tok:
                nested = _resolve_path_token(host_parent, tok)
                if not nested.is_file():
                    raise FileNotFoundError(f"嵌套 filelist 不存在: {nested}（自 {path_log}）")
                _consume_one_filelist(
                    nested,
                    output_path=output_path,
                    path_absolute=path_absolute,
                    outcome=outcome,
                    visited=visited,
                    sig_files=sig_files,
                    sig_seen=sig_seen,
                    depth=depth + 1,
                )
            continue

        vm = _V_LINE.match(s)
        if vm:
            tok = _parse_first_path_token(vm.group(1))
            if tok:
                src = _resolve_path_token(host_parent, tok)
                if not src.is_file():
                    raise FileNotFoundError(f"-v 源文件不存在: {src}（自 {path_log}）")
                outcome.head_lines.append(
                    format_listed_path(src, output_path, absolute=path_absolute)
                )
            continue

        ym = _Y_LINE.match(s)
        if ym:
            tok = _parse_first_path_token(ym.group(1))
            if tok:
                ydir = _resolve_path_token(host_parent, tok)
                if not ydir.is_dir():
                    raise FileNotFoundError(f"-y 目录不存在: {ydir}（自 {path_log}）")
                disp = format_listed_path(ydir, output_path, absolute=path_absolute)
                outcome.head_lines.append(f"-y {disp}")
            continue

        im = _INCDIR.match(s)
        if im:
            inc = im.group(2) or im.group(3) or ""
            if inc:
                resolved = _resolve_incdir(path_log, inc)
                outcome.incdirs.append(resolved)
                outcome.head_lines.append(
                    _format_incdir_line(resolved, output_path, absolute=path_absolute)
                )
            continue

        dm = _DEFINE.match(s)
        if dm:
            k, v = dm.group(1), (dm.group(2) or "").strip()
            outcome.defines[k] = v
            outcome.head_lines.append(_format_define_line(k, v))
            continue

        if s.startswith("+"):
            outcome.head_lines.append(s)
            continue

        token = s.rstrip(";").strip()
        if not token:
            continue
        cand = _resolve_path_token(host_parent, token)
        if cand.is_file() and _is_hdl_source_file(cand):
            outcome.head_lines.append(
                format_listed_path(cand, output_path, absolute=path_absolute)
            )
            continue

        if cand.exists():
            outcome.head_lines.append(
                format_listed_path(cand, output_path, absolute=path_absolute)
            )
            continue

        outcome.head_lines.append(s)


def load_prelude_files_with_signature(
    paths: list[Path],
    *,
    output_path: Path,
    path_absolute: bool = False,
) -> tuple[PreludeOutcome, str]:
    """按 ``-p`` 顺序展开 prelude：filelist 支持嵌套 ``-f``；HDL 源文件则单行写入。

    Returns:
        (解析结果, 供 ``FileParseArchive`` 使用的 prelude 签名)。
    """
    out = PreludeOutcome()
    sig_files: list[Path] = []
    sig_seen: set[Path] = set()

    if not paths:
        return out, prelude_signature_from_files(sig_files)

    for p0 in paths:
        p_exp = p0.expanduser()
        p = logical_abs(p_exp)
        if not p.exists():
            raise FileNotFoundError(f"prelude 不存在: {p}")
        if _is_hdl_source_file(p):
            if not p.is_file():
                raise FileNotFoundError(f"prelude 源不是普通文件: {p}")
            out.head_lines.append(format_listed_path(p, output_path, absolute=path_absolute))
            _record_sig(p, sig_files, sig_seen)
            continue

        visited: set[Path] = set()
        _consume_one_filelist(
            p,
            output_path=output_path,
            path_absolute=path_absolute,
            outcome=out,
            visited=visited,
            sig_files=sig_files,
            sig_seen=sig_seen,
            depth=0,
        )

    return out, prelude_signature_from_files(sig_files)


def load_prelude_files(
    paths: list[Path],
    *,
    output_path: Path | None = None,
    path_absolute: bool = False,
) -> PreludeOutcome:
    """兼容旧调用：未给 ``output_path`` 时用 ``paths[0].parent/_prelude_out.f`` 仅用于路径格式锚点。"""
    if not paths:
        return PreludeOutcome()
    anchor = output_path or (paths[0].parent / "_prelude_list_out.f")
    outcome, _ = load_prelude_files_with_signature(
        paths, output_path=anchor, path_absolute=path_absolute
    )
    return outcome
