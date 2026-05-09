from __future__ import annotations

from api.events.filelist_build import OnSessionEndAPI


@OnSessionEndAPI.register
def sink_close_parse_save(cb: OnSessionEndAPI) -> None:
    """关闭本会话绑定的解析复用存储（`--save`）。"""
    store = getattr(cb.ctx, "save", None)
    if store is not None:
        store.close()
