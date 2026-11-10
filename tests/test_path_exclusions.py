from core.path_exclude import PathExclusions, path_is_excluded


def test_compiled_scope_matches_file_directory_and_identity_rules(tmp_path):
    tree = tmp_path / 'tree'; tree.mkdir()
    child = tree / 'child.v'; child.write_text('')
    exact = tmp_path / 'exact.v'; exact.write_text('')
    allowed = tmp_path / 'allowed.v'; allowed.write_text('')
    for paths in [[], [exact], [tree], [tree, exact], [exact, tree, exact]]:
        compiled = PathExclusions(paths)
        for candidate in [tree, child, exact, allowed, tree / '..' / 'exact.v']:
            assert path_is_excluded(candidate, compiled) == path_is_excluded(candidate, paths)


def test_new_session_recompiles_exclusion_anchor_type(tmp_path):
    anchor = tmp_path / 'anchor'; anchor.write_text('')
    first = PathExclusions([anchor])
    child = anchor / 'child.v'
    assert not path_is_excluded(child, first)
    anchor.unlink(); anchor.mkdir(); child.write_text('')
    assert path_is_excluded(child, PathExclusions([anchor]))
