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
    """Strip always/initial/final style procedural blocks heuristically before regex scan."""

    source_text: str = Field(description="Source text, typically already comment-stripped")
    dropped_text: str = Field(default="", description="Output with procedural blocks removed")


class SqueezeForDependencyScanAPI(BaseAPI):
    """Full squeeze pipeline (comments + procedural drop) used before module/instance regex scan."""

    source_text: str = Field(description="Flattened active-branch source text")
    squeezed_text: str = Field(default="", description="Output ready for dependency regex scan")


class ScanVerilogForDependenciesAPI(BaseAPI):
    """After squeeze: extract defined modules, referenced types, and `include strings."""

    scanned_text: str = Field(description="Squeezed flat source used for instance/module regex scan")
    defined_modules: list[str] = Field(default_factory=list, description="module names defined in this fragment")
    referenced_modules: list[str] = Field(
        default_factory=list,
        description="Referenced module/type names from instances and bind",
    )
    include_paths: list[str] = Field(
        default_factory=list,
        description="Paths taken from include directives in the scanned fragment",
    )
