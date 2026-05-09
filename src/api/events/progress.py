from __future__ import annotations

from pydantic import Field

from api.base import BaseAPI


class OnProgressAPI(BaseAPI):
    """解析或搜索路径上的进度切片，供终端动态展示与技术日志选用。"""

    phase: str = Field(description="阶段名，例如索引、解析依赖、写出文件列表")
    current: int = Field(description="已完成的计数，单调递增的一个维度")
    total: int | None = Field(default=None, description="该维度计划总量，未知时为空以便无限进度样式")
    message: str | None = Field(default=None, description="当前项或子步骤的人类可读说明")
