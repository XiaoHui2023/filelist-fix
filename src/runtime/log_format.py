from __future__ import annotations

from collections.abc import Sequence


def lines_block(title: str, items: Sequence[str], *, empty: str = "(none)") -> str:
    """把一段列表格式化成带标题的缩进块，便于写入文件日志。"""

    seq = list(items)
    if not seq:
        return f"{title}: {empty}"
    lines = [f"{title} ({len(seq)}):"]
    lines.extend(f"  - {item}" for item in seq)
    return "\n".join(lines)
