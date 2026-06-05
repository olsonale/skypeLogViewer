from skype_log_viewer.search import filter_indices, matching_indices, next_index

ITEMS = ["hello world", "goodbye", "Hello again", "nothing"]


def test_filter_indices_empty_query_returns_all():
    assert filter_indices(ITEMS, "") == [0, 1, 2, 3]


def test_filter_indices_case_insensitive():
    assert filter_indices(ITEMS, "hello") == [0, 2]


def test_matching_indices_empty_query_returns_none():
    assert matching_indices(ITEMS, "") == []


def test_matching_indices_finds_substrings():
    assert matching_indices(ITEMS, "o") == [0, 1, 2, 3]


def test_next_index_forward_wraps():
    matches = [0, 2]
    assert next_index(matches, current=-1, forward=True) == 0
    assert next_index(matches, current=0, forward=True) == 2
    assert next_index(matches, current=2, forward=True) == 0  # wrap


def test_next_index_backward_wraps():
    matches = [0, 2]
    assert next_index(matches, current=3, forward=False) == 2
    assert next_index(matches, current=2, forward=False) == 0
    assert next_index(matches, current=0, forward=False) == 2  # wrap


def test_next_index_no_matches_returns_none():
    assert next_index([], current=0, forward=True) is None


from skype_log_viewer.search import grouped_matches


# (group_id, items) pairs — group ids are arbitrary labels, not indices.
GROUPS = [
    ("g0", ["hello world", "goodbye"]),
    ("g1", ["Hello again", "nothing"]),
    ("g2", []),
]


def test_grouped_matches_spans_groups_in_order():
    # "hello" matches item 0 of g0 and item 0 of g1, returned as (group, item) pairs
    assert grouped_matches(GROUPS, "hello") == [(0, 0), (1, 0)]


def test_grouped_matches_case_insensitive():
    assert grouped_matches(GROUPS, "HELLO") == [(0, 0), (1, 0)]


def test_grouped_matches_empty_query_returns_none():
    assert grouped_matches(GROUPS, "") == []


def test_grouped_matches_no_matches_returns_none():
    assert grouped_matches(GROUPS, "zzz") == []


def test_grouped_matches_uses_key_projection():
    groups = [("g0", [{"t": "alpha"}, {"t": "beta"}]),
              ("g1", [{"t": "ALPHA"}])]
    assert grouped_matches(groups, "alpha", key=lambda d: d["t"]) == [(0, 0), (1, 0)]
