from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    id: str
    sender_id: str
    sender_name: str          # resolved display name, or "You" for the export owner
    timestamp: datetime       # timezone-aware (UTC) instant the message arrived
    msgtype: str              # raw Skype message type, e.g. "RichText"
    clean_text: str           # cleaned, speech-friendly text
    is_system: bool           # True for join/leave/topic and other system events


@dataclass
class Conversation:
    id: str
    display_name: str
    is_group: bool
    member_count: int
    messages: list[Message] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def has_messages(self) -> bool:
        """True if at least one real (non-system) message was stored.

        A conversation whose only entries are system events (joins, member
        adds, topic changes) "does not actually contain messages" and is
        treated as empty for the conversation-list filter.
        """
        return any(not m.is_system for m in self.messages)


@dataclass
class ExportData:
    user_id: str
    conversations: list[Conversation]
