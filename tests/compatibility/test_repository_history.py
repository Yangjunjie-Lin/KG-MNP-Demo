from tests.compatibility.repository_history import assert_repository_history


def test_fixed_source_objects_and_all_ancestor_authorities_remain_available():
    assert_repository_history()
