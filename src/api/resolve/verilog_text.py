from __future__ import annotations

from pydantic import Field

from api.base import BaseAPI


class JoinContinuedLinesAPI(BaseAPI):
    """Fold backslash line continuations before preprocessing."""

    raw_text: str = Field(description="Raw file text as read from disk")
    joined_text: str = Field(default="", description="Output after joining \\ continuations")


class MaskPreprocessorCommentsAPI(BaseAPI):
    """Mask comments before directive evaluation, preserving include strings."""

    source_text: str = Field(description="Joined source without protected regions")
    masked_text: str = Field(default="", description="Comment-free source for preprocessing")


class StripVerilogCommentsAPI(BaseAPI):
    """Remove // and /* */ while preserving string literals, for dependency scanning."""

    source_text: str = Field(description="Verilog/SystemVerilog source fragment")
    stripped_text: str = Field(default="", description="Output with block and line comments removed")


class DropAlwaysishBlocksAPI(BaseAPI):
    """Heuristically strip procedural blocks unrelated to instantiation (always family, task, specify, …)."""

    source_text: str = Field(description="Source text, typically already comment-stripped")
    dropped_text: str = Field(
        default="",
        description="Output with always/initial/final, task/endtask, specify/endspecify, etc. removed; generate/endgenerate retained",
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
    semantic_text: str | None = Field(default=None, description="Active source before lossy instance filtering; declaration and scope authority")
    defined_modules: list[str] = Field(
        default_factory=list,
        description="本片段内定义的 module 名、Verilog ``primitive``（UDP）名，以及 ``package`` 名",
    )
    referenced_modules: list[str] = Field(
        default_factory=list,
        description="实例与 bind 中的用户模块类型名，以及 import 和 pkg::成员 中的包名（内建门原语不入列）",
    )
    include_paths: list[str] = Field(
        default_factory=list,
        description="Paths taken from include directives in the scanned fragment",
    )
