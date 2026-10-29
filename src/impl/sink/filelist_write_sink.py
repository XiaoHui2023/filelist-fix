from __future__ import annotations

from api.events.filelist_build import OnFilelistWriteAPI
from pathlib import Path
from tempfile import NamedTemporaryFile
import os


@OnFilelistWriteAPI.register
def sink_write_filelist(cb: OnFilelistWriteAPI) -> None:
    """按事件载荷将 filelist 原子写入指定路径。"""
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                dir=cb.output_path.parent, prefix=".filelist-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(cb.text)
        os.replace(temporary, cb.output_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
