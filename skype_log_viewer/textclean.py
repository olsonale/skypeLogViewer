from __future__ import annotations

import html
import re
from typing import Callable, Optional

_SYSTEM_TYPES = {"InviteFreeRelationshipChanged/Initialized", "Notice", "PopCard"}

_TAG_RE = re.compile(r"<[^>]+>")
_SS_RE = re.compile(r"<ss[^>]*>(.*?)</ss>", re.DOTALL)
_AT_RE = re.compile(r"<at[^>]*>(.*?)</at>", re.DOTALL)
_A_RE = re.compile(r'<a\s+[^>]*?href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
_LEGACY_RE = re.compile(r"<legacyquote>.*?</legacyquote>", re.DOTALL)
_QUOTE_RE = re.compile(r"<quote([^>]*)>(.*?)</quote>", re.DOTALL)
_ORIGINAL_NAME_RE = re.compile(r'<OriginalName\s+v="([^"]*)"')


def is_system_event(msgtype: str) -> bool:
    return msgtype.startswith("ThreadActivity/") or msgtype in _SYSTEM_TYPES


def _attr(source: str, name: str) -> str:
    m = re.search(name + r'="([^"]*)"', source)
    return m.group(1) if m else ""


def _tag_text(source: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", source, re.DOTALL)
    return m.group(1).strip() if m else ""


def _format_link(href: str, text: str) -> str:
    text = _TAG_RE.sub("", text).strip()
    href = href.strip()
    if not text or text == href:
        return href
    return f"{text} ({href})"


def _strip_tags(source: str) -> str:
    source = _SS_RE.sub(lambda m: m.group(1), source)
    source = _AT_RE.sub(lambda m: m.group(1), source)
    source = _A_RE.sub(lambda m: _format_link(m.group(1), m.group(2)), source)
    source = _TAG_RE.sub("", source)
    return html.unescape(source).strip()


def _replace_quotes(source: str) -> str:
    def repl(m: re.Match) -> str:
        attrs, body = m.group(1), m.group(2)
        author = _attr(attrs, "authorname") or _attr(attrs, "author")
        body = _LEGACY_RE.sub("", body)
        body = _strip_tags(body).strip()
        if author:
            return f'Quote from {author}: "{body}". '
        return f'Quote: "{body}". '

    return _QUOTE_RE.sub(repl, source)


def _clean_richtext(content: str) -> str:
    return _strip_tags(_replace_quotes(content)).strip()


def _clean_media(content: str, msgtype: str) -> str:
    obj_type = _attr(content, "type")
    if msgtype == "Poll" or obj_type == "Poll":
        title = _attr(content, "title")
        return f"[Poll: {title}]" if title else "[Poll]"
    if obj_type.startswith("Picture"):
        return "[Photo]"
    if obj_type.startswith("Audio"):
        return "[Voice message]"
    if obj_type.startswith("Video"):
        return "[Video]"
    if obj_type.startswith("File"):
        m = _ORIGINAL_NAME_RE.search(content)
        name = m.group(1) if m else ""
        return f"[File: {name}]" if name else "[File]"
    return "[Attachment]"


def _clean_call(content: str) -> str:
    dur = re.search(r"<duration>(\d+)</duration>", content)
    if dur:
        seconds = int(dur.group(1))
        unit = "second" if seconds == 1 else "seconds"
        return f"[Call, {seconds} {unit}]"
    ctype = _attr(content, "type")
    if ctype == "started":
        return "[Call started]"
    return "[Call ended]"


def _clean_system(content: str, msgtype: str, look: Callable[[str], str]) -> str:
    if msgtype == "ThreadActivity/AddMember":
        init, tgt = _tag_text(content, "initiator"), _tag_text(content, "target")
        if init == tgt:
            return f"[{look(tgt)} joined the chat]"
        return f"[{look(init)} added {look(tgt)}]"
    if msgtype == "ThreadActivity/DeleteMember":
        init, tgt = _tag_text(content, "initiator"), _tag_text(content, "target")
        if init == tgt:
            return f"[{look(tgt)} left the chat]"
        return f"[{look(init)} removed {look(tgt)}]"
    if msgtype == "ThreadActivity/TopicUpdate":
        return f'[Topic changed to "{_tag_text(content, "value")}"]'
    if msgtype == "ThreadActivity/RoleUpdate":
        return "[Member roles updated]"
    if msgtype in ("ThreadActivity/HistoryDisclosedUpdate", "ThreadActivity/JoiningEnabledUpdate"):
        return "[Chat settings changed]"
    if msgtype == "Notice":
        return "[Notice]"
    if msgtype == "PopCard":
        return "[Card]"
    return f"[{msgtype.split('/')[-1]}]"


def clean_content(
    content: Optional[str],
    msgtype: str,
    name_lookup: Optional[Callable[[str], str]] = None,
) -> str:
    content = content or ""
    look = name_lookup or (lambda x: x)
    if msgtype in ("RichText", "Text"):
        return _clean_richtext(content)
    if msgtype == "Poll" or msgtype.startswith("RichText/Media") or msgtype == "RichText/UriObject":
        return _clean_media(content, msgtype)
    if msgtype == "Event/Call":
        return _clean_call(content)
    if is_system_event(msgtype):
        return _clean_system(content, msgtype, look)
    return _clean_richtext(content)
