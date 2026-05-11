from __future__ import annotations

from typing import Any, TypeVar

from callback import Callback

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

    def fire(self, api: type[TApi], **kwargs: Any) -> TApi:
        """触发已注册的同步回调链并返回载荷实例。"""
        return api.trigger(ctx=self, **kwargs)
