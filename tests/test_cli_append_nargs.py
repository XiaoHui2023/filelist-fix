from __future__ import annotations

from runtime.cli_parser import build_parser, flatten_append_groups


def test_flatten_append_groups_order() -> None:
    assert flatten_append_groups([["a", "b"], ["c"]]) == ["a", "b", "c"]
    assert flatten_append_groups(None) == []
    assert flatten_append_groups([]) == []


def test_cli_multi_value_after_one_flag_equivalent_to_repeat() -> None:
    once = build_parser().parse_args(
        ["-s", "r1", "r2", "-t", "m1", "m2", "-o", "out.f"],
    )
    repeat = build_parser().parse_args(
        ["-s", "r1", "-s", "r2", "-t", "m1", "-t", "m2", "-o", "out.f"],
    )
    assert flatten_append_groups(once.sources) == flatten_append_groups(repeat.sources)
    assert flatten_append_groups(once.tops) == flatten_append_groups(repeat.tops)


def test_cli_exclude_short_x_and_multi_value() -> None:
    a = build_parser().parse_args(
        ["-s", "r1", "-t", "m1", "-o", "out.f", "-x", "e1", "e2"],
    )
    assert flatten_append_groups(a.excludes) == ["e1", "e2"]
    b = build_parser().parse_args(
        ["-s", "r1", "-t", "m1", "-o", "out.f", "--exclude", "a", "--exclude", "b"],
    )
    assert flatten_append_groups(b.excludes) == ["a", "b"]
