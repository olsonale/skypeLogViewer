from __future__ import annotations

from typing import Callable, Optional, Sequence

Key = Callable[[object], str]


def _identity(item: object) -> str:
    return item  # type: ignore[return-value]


def filter_indices(items: Sequence, query: str, key: Key = _identity) -> list[int]:
    """Indices of items containing query (case-insensitive). Empty query -> all indices."""
    if not query:
        return list(range(len(items)))
    q = query.casefold()
    return [i for i, it in enumerate(items) if q in key(it).casefold()]


def matching_indices(items: Sequence, query: str, key: Key = _identity) -> list[int]:
    """Indices of items containing query. Empty query -> no matches."""
    if not query:
        return []
    q = query.casefold()
    return [i for i, it in enumerate(items) if q in key(it).casefold()]


def next_index(matches: Sequence[int], current: int, forward: bool = True) -> Optional[int]:
    """Next match strictly past `current`, wrapping around. None if no matches."""
    if not matches:
        return None
    if forward:
        for m in matches:
            if m > current:
                return m
        return matches[0]
    for m in reversed(matches):
        if m < current:
            return m
    return matches[-1]


def grouped_matches(groups: Sequence, query: str, key: Key = _identity) -> list[tuple[int, int]]:
    """(group_index, item_index) pairs for items containing query (case-insensitive).

    `groups` is a sequence of (group_id, items) pairs; the group_id is ignored
    for indexing — the returned group index is the position in `groups`. Empty
    query -> [] (consistent with matching_indices). Groups in input order, items
    in input order within each group.
    """
    if not query:
        return []
    q = query.casefold()
    pairs: list[tuple[int, int]] = []
    for gi, (_group_id, items) in enumerate(groups):
        for ii, it in enumerate(items):
            if q in key(it).casefold():
                pairs.append((gi, ii))
    return pairs
