from __future__ import annotations

from pydantic import Field

from api.base import BaseAPI


class OnProgressAPI(BaseAPI):
    """Coarse progress slice for terminal and optional debug logging."""

    phase: str = Field(description="Phase label, e.g. parse, write filelist")
    current: int = Field(description="Completed count along one progress dimension")
    total: int | None = Field(default=None, description="Planned total for that dimension; None if unknown")
    message: str | None = Field(default=None, description="Optional human-readable sub-step detail")
