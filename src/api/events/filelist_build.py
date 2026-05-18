from __future__ import annotations

from pathlib import Path

from pydantic import Field

from api.base import BaseAPI


class OnPreludeLoadedAPI(BaseAPI):
    """Emitted after prelude filelist snippets are merged into defines and incdirs."""

    prelude_path_count: int = Field(description="Number of prelude files loaded this run")
    define_count: int = Field(description="Number of text macros from prelude +define")
    incdir_count: int = Field(description="Number of +incdir+ paths from prelude")


class OnModuleResolveMissAPI(BaseAPI):
    """Emitted when fd/rg cannot locate a source file for a module name (at most once per name per run)."""

    module_name: str = Field(description="Module name queued for parsing but not found on disk")


class OnIncludeResolveMissAPI(BaseAPI):
    """Emitted when an active `` `include`` cannot be resolved (at most once per (from_file, spec) per run)."""

    include_spec: str = Field(description="Include path as written in the directive (after stripping)")
    from_file: Path = Field(description="Source file containing that `` `include`` line")


class OnModuleIndexInconsistentAPI(BaseAPI):
    """Emitted when a module maps to a file that is not yet in the parsed-files set."""

    module_name: str = Field(description="Module name that triggered the consistency check")


class OnSourceParsedAPI(BaseAPI):
    """Emitted after one source path is parsed (or served from persisted parse reuse)."""

    path: Path = Field(description="Absolute path to the parsed source file")
    cache_hit: bool = Field(description="True if persisted parse results for this file were reused unchanged")
    defined_count: int = Field(description="Number of module names defined in this file")
    referenced_count: int = Field(description="Number of module names referenced from this file")


class OnClosureEmptyAPI(BaseAPI):
    """Emitted when the dependency closure has no file-level reference edges."""


class OnBuildTopologyReadyAPI(BaseAPI):
    """Emitted after topological sort produced the ordered file path list."""

    ordered_file_count: int = Field(description="Number of file paths in the sorted filelist body")
    head_line_count: int = Field(description="Number of prelude lines before the file body")


class OnFilelistWriteAPI(BaseAPI):
    """Emitted to request writing the full filelist text; impl sink performs I/O."""

    output_path: Path = Field(description="Destination filelist path")
    text: str = Field(description="Full filelist text including trailing newline")


class OnSessionEndAPI(BaseAPI):
    """Emitted once at session end to release cross-step resources (e.g. save store handle)."""
