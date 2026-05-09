from __future__ import annotations

from typing import Any, TypeVar

from callback import Callback

TApi = TypeVar("TApi", bound=Callback)


class AppContext:
    """承载一次运行所需的控制台、日志、进度条句柄与对外事件触发。"""

    def __init__(
        self,
        logger: Any,
        console: Any,
        alive_bar: Any | None = None,
    ) -> None:
        self.logger = logger
        self.console = console
        self.alive_bar = alive_bar

    def fire(self, api: type[TApi], **kwargs: Any) -> TApi:
        """触发已注册的同步回调链并返回载荷实例。"""
        return api.trigger(ctx=self, **kwargs)
