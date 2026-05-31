from __future__ import annotations

import hashlib
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path

from .model import Conversation, ExportData, Message
from .names import NameResolver, pretty_id
from .textclean import clean_content, is_system_event


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_export(path: str | Path) -> ExportData:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    user_id = raw.get("userId", "")
    conversations_raw = raw.get("conversations", [])

    resolver = NameResolver(user_id)
    for conv in conversations_raw:
        for m in conv.get("MessageList", []):
            resolver.learn(m.get("from"), m.get("displayName"))

    conversations: list[Conversation] = []
    for conv in conversations_raw:
        messages: list[Message] = []
        for m in conv.get("MessageList", []):
            mtype = m.get("messagetype", "")
            sender_id = m.get("from", "")
            messages.append(
                Message(
                    id=m.get("id", ""),
                    sender_id=sender_id,
                    sender_name=resolver.name_for(sender_id),
                    timestamp=_parse_time(m.get("originalarrivaltime")),
                    msgtype=mtype,
                    clean_text=clean_content(m.get("content"), mtype, name_lookup=resolver.name_for),
                    is_system=is_system_event(mtype),
                )
            )
        messages.sort(key=lambda x: x.timestamp)

        conv_id = conv.get("id", "")
        is_group = "@thread." in conv_id
        thread_props = conv.get("threadProperties") or {}
        member_count = int(thread_props.get("membercount") or (0 if is_group else 2))

        conversations.append(
            Conversation(
                id=conv_id,
                display_name=conv.get("displayName") or pretty_id(conv_id),
                is_group=is_group,
                member_count=member_count,
                messages=messages,
            )
        )

    conversations.sort(key=lambda c: (c.display_name or "").casefold())
    return ExportData(user_id=user_id, conversations=conversations)


CACHE_VERSION = 1


def _cache_path(source: str | Path, cache_dir: str | Path) -> Path:
    source = Path(source)
    st = source.stat()
    key = f"{source.resolve()}|{st.st_size}|{int(st.st_mtime)}|v{CACHE_VERSION}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{digest}.pickle"


def load_with_cache(path: str | Path, cache_dir: str | Path) -> ExportData:
    """Load from cache if a fresh pickle exists for this file, else parse and cache."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(path, cache_dir)

    if cache_file.exists():
        try:
            return pickle.loads(cache_file.read_bytes())
        except Exception:
            pass  # corrupt/incompatible cache -> reparse

    data = load_export(path)
    try:
        cache_file.write_bytes(pickle.dumps(data))
    except Exception:
        pass  # caching is best-effort; never block on it
    return data
