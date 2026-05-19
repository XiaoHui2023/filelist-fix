from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.path_logical import logical_abs


def defines_signature(defines: dict[str, str]) -> str:
    """prelude 与单文件解析共用的 ``+define+`` 快照摘要。"""
    payload = json.dumps(defines, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def incdirs_canonical_list(incdirs: list[Path]) -> list[str]:
    """已解析的 ``+incdir+`` 路径，排序后用于存档与比较。"""
    return sorted({str(logical_abs(p)) for p in incdirs})


def incdirs_json(incdirs: list[Path]) -> str:
    return json.dumps(incdirs_canonical_list(incdirs), separators=(",", ":"))


def parse_context_compatible(
    cached_defines_sig: str,
    cached_incdirs_json: str,
    *,
    defines: dict[str, str],
    incdirs: list[Path],
) -> bool:
    """缓存行是否仍可用于本轮解析（宏一致；存档 incdir 为当前 incdir 的子集）。"""
    if not cached_defines_sig:
        return False
    if cached_defines_sig != defines_signature(defines):
        return False
    try:
        cached_set = set(json.loads(cached_incdirs_json))
    except (json.JSONDecodeError, TypeError):
        return False
    current_set = set(incdirs_canonical_list(incdirs))
    return cached_set <= current_set
