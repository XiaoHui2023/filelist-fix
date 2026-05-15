from __future__ import annotations

from pydantic import Field

from api.base import BaseAPI


class JoinContinuedLinesAPI(BaseAPI):
    """Fold backslash line continuations before preprocessing."""

    raw_text: str = Field(description="Raw file text as read from disk")
    joined_text: str = Field(default="", description="Output after joining \\ continuations")


class StripVerilogCommentsAPI(BaseAPI):
    """Remove // and /* */ while preserving string literals, for dependency scanning."""

    source_text: str = Field(description="Verilog/SystemVerilog source fragment")
    stripped_text: str = Field(default="", description="Output with block and line comments removed")


class DropAlwaysishBlocksAPI(BaseAPI):
    """Heuristically strip procedural blocks unrelated to instantiation (always family, task, specify, …)."""

    source_text: str = Field(description="Source text, typically already comment-stripped")
    dropped_text: str = Field(
        default="",
        description="Output with always/initial/final, task/endtask, specify/endspecify, etc. removed",
    )


class SqueezeForDependencyScanAPI(BaseAPI):
    """Ordered squeeze pipeline before module/instance regex scan."""

    source_text: str = Field(description="Flattened active-branch source text")
    squeezed_text: str = Field(
        default="",
        description="After comments, procedural-block drop, decl-noise blanking, port-header strip, and instance-port skeletonization",
    )


class ScanVerilogForDependenciesAPI(BaseAPI):
    """After squeeze: extract defined modules, referenced types, and `include strings."""

    scanned_text: str = Field(description="Squeezed flat source used for instance/module regex scan")
    defined_modules: list[str] = Field(
        default_factory=list,
        description="本片段内定义的 module 名，以及 Verilog ``primitive``（UDP）名",
    )
    referenced_modules: list[str] = Field(
        default_factory=list,
        description="实例与 bind 中出现的用户定义模块类型名（内建门原语不入列，不参与闭包解析）",
    )
    include_paths: list[str] = Field(
        default_factory=list,
        description="Paths taken from include directives in the scanned fragment",
    )
