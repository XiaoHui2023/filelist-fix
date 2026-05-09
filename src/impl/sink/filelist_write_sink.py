from __future__ import annotations

from api.events.filelist_build import OnFilelistWriteAPI


@OnFilelistWriteAPI.register
def sink_write_filelist(cb: OnFilelistWriteAPI) -> None:
    """按事件载荷将 filelist 原子写入指定路径。"""
    cb.output_path.write_text(cb.text, encoding="utf-8")
