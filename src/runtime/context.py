from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

from callback import Callback

from core.path_logical import logical_abs

TApi = TypeVar("TApi", bound=Callback)


class AppContext:
    """承载一次运行所需的控制台、日志、Rich 进度与对外事件触发。"""

    def __init__(
        self,
        logger: Any,
        console: Any,
        rich_progress: Any | None = None,
        progress_task_id: Any | None = None,
        save: Any | None = None,
        dependency_debug_dump: Any | None = None,
    ) -> None:
        self.logger = logger
        self.console = console
        self.rich_progress = rich_progress
        self.progress_task_id = progress_task_id
        self.save = save
        self.dependency_debug_dump = dependency_debug_dump
        self.include_resolve_miss_seen: set[tuple[str, str]] = set()
        self.include_resolve_miss_order: list[tuple[str, Path]] = []
        self._include_miss_specs_by_file: dict[str, list[str]] = {}
        self.exit_code: int | None = None

    def note_include_miss(self, from_file: Path, spec: str) -> None:
        """记录一次未解析的 `` `include``（同一文件内同一 spec 只记一次）。"""
        path = logical_abs(from_file)
        key = (str(path), spec)
        if key in self.include_resolve_miss_seen:
            return
        self.include_resolve_miss_seen.add(key)
        self.include_resolve_miss_order.append((spec, path))
        fp = str(path)
        bucket = self._include_miss_specs_by_file.setdefault(fp, [])
        if spec not in bucket:
            bucket.append(spec)

    def pop_include_miss_specs(self, from_file: Path) -> list[str]:
        """取出并清除某源文件上已收集、尚未上报的 include spec 列表。"""
        return self._include_miss_specs_by_file.pop(str(logical_abs(from_file)), [])

    def request_exit(self, code: int) -> None:
        """请求以给定状态码结束进程（由 ``__main__`` 在编排返回后 ``sys.exit``）。"""
        self.exit_code = code

    def fire(self, api: type[TApi], **kwargs: Any) -> TApi:
        """触发已注册的同步回调链并返回载荷实例。"""
        return api.trigger(ctx=self, **kwargs)
