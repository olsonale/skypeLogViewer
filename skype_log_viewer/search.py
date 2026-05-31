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
