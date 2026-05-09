from core.hdl_extensions import HD_SOURCE_EXTENSIONS, rg_include_globs


def test_sv_and_sv_glob_present() -> None:
    assert "sv" in HD_SOURCE_EXTENSIONS
    assert any(g.endswith(".sv") for g in rg_include_globs())
