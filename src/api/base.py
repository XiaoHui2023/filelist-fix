from __future__ import annotations

from typing import Any

from callback import Callback
from pydantic import Field


class BaseAPI(Callback):
    """同步事件基类：载荷字段即一次通知的数据，分层处理函数登记在子类上。"""

    ctx: Any = Field(description="Runtime context: console, logger, progress task, save, fire()")
