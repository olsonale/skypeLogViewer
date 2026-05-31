from __future__ import annotations

from typing import Optional


def pretty_id(skype_id: str) -> str:
    """Turn '8:bob' / '8:live:.cid.x' into a friendlier form by dropping the '8:' prefix."""
    if skype_id.startswith("8:"):
        return skype_id[2:]
    return skype_id


class NameResolver:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self._map: dict[str, str] = {}

    def learn(self, sender_id: Optional[str], display_name: Optional[str]) -> None:
        if sender_id and display_name and sender_id not in self._map:
            self._map[sender_id] = display_name

    def name_for(self, sender_id: str) -> str:
        if sender_id == self.user_id:
            return "You"
        return self._map.get(sender_id) or pretty_id(sender_id)
