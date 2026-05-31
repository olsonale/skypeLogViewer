# Skype Log Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a keyboard-driven, screen-reader-accessible desktop app (Python 3.13 + wxPython) that loads an exported Skype `messages.json`, lists conversations A–Z, and lets the user step through messages with a per-message detail field and in-conversation search.

**Architecture:** Pure-logic core (model, text cleaning, name resolution, formatting, loader+cache, config, search) built test-first with pytest, plus a thin wxPython UI layer (`ui/`) wired on top. The export is parsed once into in-memory dataclasses, with cleaned text/resolved names computed at load time and pickled to a cache keyed by file path+size+mtime so relaunches are near-instant.

**Tech Stack:** Python 3.13, wxPython 4.2 (native Windows controls → MSAA/UIA accessibility), pytest, dependencies managed entirely with **uv** (`uv add`, `uv run`).

**Design spec:** `docs/superpowers/specs/2026-05-31-skype-log-viewer-design.md`

---

## File Structure

```
skypeLogViewer/
  pyproject.toml                    # uv-managed project + deps
  .gitignore
  README.md
  skype_log_viewer/
    __init__.py
    __main__.py                     # entry: uv run python -m skype_log_viewer
    model.py                        # Message, Conversation, ExportData dataclasses
    formatting.py                   # time + preview + date-label + row formatting
    textclean.py                    # raw HTML/XML content -> clean speech-friendly text
    names.py                        # NameResolver + _pretty_id
    loader.py                       # JSON parse -> model; pickle cache
    config.py                       # config + per-conversation position persistence
    search.py                       # filter + find-next/previous (pure functions)
    ui/
      __init__.py
      main_frame.py                 # main window, four panes, menus, key handling
      info_dialog.py                # Ctrl+I conversation info
      shortcuts_dialog.py           # F1 shortcuts list
  tests/
    __init__.py
    fixtures/sample_export.json
    test_formatting.py
    test_textclean.py
    test_names.py
    test_loader.py
    test_config.py
    test_search.py
    test_ui_smoke.py
```

Each logic module has one responsibility and no UI imports, so it is unit-testable in isolation. The UI imports the logic modules and owns all wx state.

---

## Task 1: Project scaffold with uv

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `skype_log_viewer/__init__.py`, `skype_log_viewer/ui/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "skype-log-viewer"
version = "0.1.0"
description = "Accessible desktop viewer for exported Skype logs"
requires-python = ">=3.13"
dependencies = ["wxpython>=4.2.2"]

[dependency-groups]
dev = ["pytest>=8"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create empty package files**

Create `skype_log_viewer/__init__.py`, `skype_log_viewer/ui/__init__.py`, and `tests/__init__.py` each containing a single comment line:

```python
# Skype Log Viewer
```

- [ ] **Step 4: Sync the environment with uv**

Run: `uv sync`
Expected: uv creates `.venv`, resolves and installs wxPython + pytest, writes `uv.lock`.

- [ ] **Step 5: Verify wxPython imports**

Run: `uv run python -c "import wx; print(wx.version())"`
Expected: prints a version like `4.2.2 ...` with no error.

- [ ] **Step 6: Verify pytest runs**

Run: `uv run pytest -q`
Expected: `no tests ran` (exit code 5) — confirms pytest is installed and discovers the `tests/` package.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .gitignore skype_log_viewer/ tests/
git commit -m "chore: scaffold uv project for Skype Log Viewer"
```

---

## Task 2: Data model (`model.py`)

**Files:**
- Create: `skype_log_viewer/model.py`
- Test: `tests/test_loader.py` (model is exercised indirectly by loader tests in Task 6; this task adds a focused construction test there is none yet, so create a tiny `tests/test_model.py`)
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_model.py`:

```python
from datetime import datetime, timezone
from skype_log_viewer.model import Message, Conversation, ExportData


def _msg(text="hi", system=False):
    return Message(
        id="1",
        sender_id="8:alice",
        sender_name="Alice",
        timestamp=datetime(2025, 3, 19, 21, 18, tzinfo=timezone.utc),
        msgtype="RichText",
        clean_text=text,
        is_system=system,
    )


def test_conversation_message_count():
    conv = Conversation(
        id="8:alice",
        display_name="Alice",
        is_group=False,
        member_count=2,
        messages=[_msg(), _msg()],
    )
    assert conv.message_count == 2


def test_export_data_holds_conversations():
    data = ExportData(user_id="8:me", conversations=[])
    assert data.user_id == "8:me"
    assert data.conversations == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.model'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/model.py`:

```python
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


@dataclass
class ExportData:
    user_id: str
    conversations: list[Conversation]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_model.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/model.py tests/test_model.py
git commit -m "feat: add core data model"
```

---

## Task 3: Formatting helpers (`formatting.py`)

**Files:**
- Create: `skype_log_viewer/formatting.py`
- Test: `tests/test_formatting.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_formatting.py`:

```python
from datetime import datetime, timezone

from skype_log_viewer.formatting import (
    format_12h,
    date_label,
    make_preview,
    format_row,
    PREVIEW_LIMIT,
)


def test_format_12h_afternoon():
    dt = datetime(2025, 3, 19, 15, 14)
    assert format_12h(dt) == "Mar 19, 2025, 3:14 PM"


def test_format_12h_midnight_is_twelve():
    dt = datetime(2025, 3, 19, 0, 5)
    assert format_12h(dt) == "Mar 19, 2025, 12:05 AM"


def test_format_12h_noon_is_twelve_pm():
    dt = datetime(2025, 3, 19, 12, 0)
    assert format_12h(dt) == "Mar 19, 2025, 12:00 PM"


def test_date_label():
    dt = datetime(2025, 3, 19, 12, 0)
    assert date_label(dt) == "Wednesday, March 19, 2025"


def test_make_preview_collapses_whitespace():
    assert make_preview("hello\n\n  world\t!") == "hello world !"


def test_make_preview_truncates_with_ellipsis():
    text = "x" * (PREVIEW_LIMIT + 50)
    out = make_preview(text)
    assert len(out) == PREVIEW_LIMIT
    assert out.endswith("…")


def test_format_row():
    dt = datetime(2025, 3, 19, 15, 14)
    assert format_row("You", dt, "hey there") == "You, Mar 19, 2025, 3:14 PM: hey there"
```

Note: `format_12h`, `date_label`, and `format_row` format the datetime **as given** (no timezone conversion), so tests are deterministic. The UTC→local conversion lives in `to_local`, applied by the UI before formatting.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_formatting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.formatting'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/formatting.py`:

```python
from __future__ import annotations

from datetime import datetime

PREVIEW_LIMIT = 256


def to_local(dt: datetime) -> datetime:
    """Convert a (UTC) datetime to the machine's local timezone."""
    return dt.astimezone()


def format_12h(dt: datetime) -> str:
    """Format as 'Mar 19, 2025, 3:14 PM'. Formats dt as-is (no tz conversion)."""
    hour = dt.hour % 12 or 12
    meridiem = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}, {hour}:{dt.minute:02d} {meridiem}"


def format_timestamp(dt: datetime) -> str:
    """Convert to local time, then format as 12-hour."""
    return format_12h(to_local(dt))


def date_label(dt: datetime) -> str:
    """Format the day as 'Wednesday, March 19, 2025' (no tz conversion)."""
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year}"


def make_preview(text: str, limit: int = PREVIEW_LIMIT) -> str:
    """Collapse whitespace and truncate to `limit` chars with an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_row(sender: str, dt: datetime, preview: str) -> str:
    """Build a message-list row label: 'You, Mar 19, 2025, 3:14 PM: hey there'."""
    return f"{sender}, {format_12h(dt)}: {preview}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_formatting.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/formatting.py tests/test_formatting.py
git commit -m "feat: add time/preview/row formatting helpers"
```

---

## Task 4: Text cleaning (`textclean.py`)

This converts raw Skype HTML/XML `content` plus `messagetype` into clean, speech-friendly text, and classifies system events. Real markup shapes (verified against the export):

- emoticon: `<ss type="laugh">:D</ss>`
- mention: `<at id="*">全部</at>`
- link: `<a href="URL">URL</a>`
- quote: `<quote author="x" authorname="Carter Temm" ...><legacyquote>[..] Carter Temm: </legacyquote>BODY<legacyquote>&lt;&lt;&lt; </legacyquote></quote>REPLY`
- photo: `<URIObject ... type="Picture.1" ...>`
- file: `<URIObject ... type="File.1" ...>...<OriginalName v="Aira new plans.docx"></OriginalName>...`
- audio: `type="Audio.1"`; video: `type="Video..."`
- poll: `<URIObject type="Poll" title="Should we switch to skype?" ...>`
- call: `<partlist type="ended" ...><part identity="s33wack"><name>s33wack</name><duration>4</duration></part></partlist>`
- add member: `<addmember><eventtime>..</eventtime><initiator>8:a</initiator><target>8:b</target></addmember>`
- delete member: `<deletemember>...<initiator>8:a</initiator><target>8:b</target></deletemember>`
- topic: `<topicupdate>...<value>SLM</value></topicupdate>`

**Files:**
- Create: `skype_log_viewer/textclean.py`
- Test: `tests/test_textclean.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_textclean.py`:

```python
from skype_log_viewer.textclean import clean_content, is_system_event


def names(skype_id):
    return {"8:alice": "Alice", "8:bob": "Bob"}.get(skype_id, skype_id)


def test_plain_richtext():
    assert clean_content("Every day I look forward.", "RichText") == "Every day I look forward."


def test_decodes_entities():
    assert clean_content("a &amp; b &lt;c&gt;", "RichText") == "a & b <c>"


def test_emoticon_keeps_inner_text():
    assert clean_content('haha <ss type="laugh">:D</ss>', "RichText") == "haha :D"


def test_mention_keeps_name():
    assert clean_content('<at id="8:bob">Bob</at> hello', "RichText") == "Bob hello"


def test_link_text_equal_to_href_shows_once():
    out = clean_content('see <a href="https://x.com">https://x.com</a>', "RichText")
    assert out == "see https://x.com"


def test_link_with_distinct_text_shows_both():
    out = clean_content('see <a href="https://x.com">my site</a>', "RichText")
    assert out == "see my site (https://x.com)"


def test_quote_formats_with_author_and_reply():
    raw = (
        '<quote author="8:bob" authorname="Bob" timestamp="1">'
        "<legacyquote>[1] Bob: </legacyquote>need to mirror you"
        "<legacyquote>&lt;&lt;&lt; </legacyquote></quote>"
        "I thought you said marry you"
    )
    out = clean_content(raw, "RichText")
    assert out == 'Quote from Bob: "need to mirror you". I thought you said marry you'


def test_photo_label():
    assert clean_content('<URIObject type="Picture.1">x</URIObject>', "RichText/UriObject") == "[Photo]"


def test_voice_label():
    assert clean_content('<URIObject type="Audio.1">x</URIObject>', "RichText/Media_AudioMsg") == "[Voice message]"


def test_video_label():
    assert clean_content('<URIObject type="Video.1">x</URIObject>', "RichText/Media_Video") == "[Video]"


def test_file_label_uses_original_name():
    raw = '<URIObject type="File.1">x<OriginalName v="report.docx"></OriginalName></URIObject>'
    assert clean_content(raw, "RichText/Media_GenericFile") == "[File: report.docx]"


def test_poll_label_uses_title():
    raw = '<URIObject type="Poll" title="Switch to Skype?">Switch?</URIObject>'
    assert clean_content(raw, "Poll") == "[Poll: Switch to Skype?]"


def test_call_with_duration():
    raw = '<partlist type="ended"><part><duration>4</duration></part></partlist>'
    assert clean_content(raw, "Event/Call") == "[Call, 4 seconds]"


def test_call_ended_no_duration():
    raw = '<partlist type="ended"></partlist>'
    assert clean_content(raw, "Event/Call") == "[Call ended]"


def test_add_member_join_when_initiator_equals_target():
    raw = "<addmember><initiator>8:alice</initiator><target>8:alice</target></addmember>"
    assert clean_content(raw, "ThreadActivity/AddMember", name_lookup=names) == "[Alice joined the chat]"


def test_add_member_added_by_other():
    raw = "<addmember><initiator>8:alice</initiator><target>8:bob</target></addmember>"
    assert clean_content(raw, "ThreadActivity/AddMember", name_lookup=names) == "[Alice added Bob]"


def test_delete_member_left():
    raw = "<deletemember><initiator>8:bob</initiator><target>8:bob</target></deletemember>"
    assert clean_content(raw, "ThreadActivity/DeleteMember", name_lookup=names) == "[Bob left the chat]"


def test_topic_update():
    raw = "<topicupdate><value>SLM</value></topicupdate>"
    assert clean_content(raw, "ThreadActivity/TopicUpdate") == '[Topic changed to "SLM"]'


def test_is_system_event():
    assert is_system_event("ThreadActivity/AddMember") is True
    assert is_system_event("Notice") is True
    assert is_system_event("RichText") is False
    assert is_system_event("Event/Call") is False


def test_none_content_is_empty_string():
    assert clean_content(None, "RichText") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_textclean.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.textclean'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/textclean.py`:

```python
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
        return f"[Call, {int(dur.group(1))} seconds]"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_textclean.py -v`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/textclean.py tests/test_textclean.py
git commit -m "feat: add message text cleaning and system-event labels"
```

---

## Task 5: Name resolution (`names.py`)

**Files:**
- Create: `skype_log_viewer/names.py`
- Test: `tests/test_names.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_names.py`:

```python
from skype_log_viewer.names import NameResolver, pretty_id


def test_own_id_resolves_to_you():
    r = NameResolver("8:me")
    assert r.name_for("8:me") == "You"


def test_learned_name_is_used():
    r = NameResolver("8:me")
    r.learn("8:alice", "Alice")
    assert r.name_for("8:alice") == "Alice"


def test_first_learned_name_wins():
    r = NameResolver("8:me")
    r.learn("8:alice", "Alice")
    r.learn("8:alice", "Alice (work)")
    assert r.name_for("8:alice") == "Alice"


def test_unknown_id_falls_back_to_pretty_id():
    r = NameResolver("8:me")
    assert r.name_for("8:live:.cid.123") == "live:.cid.123"


def test_blank_name_is_ignored():
    r = NameResolver("8:me")
    r.learn("8:alice", None)
    r.learn("8:alice", "")
    assert r.name_for("8:alice") == "alice"


def test_pretty_id_strips_prefixes():
    assert pretty_id("8:live:.cid.123") == "live:.cid.123"
    assert pretty_id("8:bob") == "bob"
    assert pretty_id("19:thread@thread.skype") == "19:thread@thread.skype"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_names.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.names'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/names.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_names.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/names.py tests/test_names.py
git commit -m "feat: add Skype-ID name resolution"
```

---

## Task 6: Export loader (`loader.py` — parse only)

**Files:**
- Create: `skype_log_viewer/loader.py`
- Create: `tests/fixtures/sample_export.json`
- Test: `tests/test_loader.py`

- [ ] **Step 1: Create the test fixture**

Create `tests/fixtures/sample_export.json`:

```json
{
  "userId": "8:me",
  "exportDate": "2025-03-19T22:39",
  "conversations": [
    {
      "id": "8:alice",
      "displayName": "Alice",
      "properties": {},
      "threadProperties": null,
      "MessageList": [
        {
          "id": "200",
          "displayName": "Alice",
          "originalarrivaltime": "2025-03-19T21:18:56.132Z",
          "messagetype": "RichText",
          "version": 1,
          "content": "second message",
          "conversationid": "8:alice",
          "from": "8:alice",
          "properties": null,
          "amsreferences": []
        },
        {
          "id": "100",
          "displayName": null,
          "originalarrivaltime": "2025-03-18T10:00:00.000Z",
          "messagetype": "RichText",
          "version": 1,
          "content": "first message",
          "conversationid": "8:alice",
          "from": "8:me",
          "properties": null,
          "amsreferences": []
        }
      ]
    },
    {
      "id": "19:grouproom@thread.skype",
      "displayName": "Trading Group",
      "properties": {},
      "threadProperties": { "membercount": 8 },
      "MessageList": [
        {
          "id": "300",
          "displayName": "Bob",
          "originalarrivaltime": "2025-03-19T12:00:00.000Z",
          "messagetype": "ThreadActivity/AddMember",
          "version": 1,
          "content": "<addmember><initiator>8:alice</initiator><target>8:bob</target></addmember>",
          "conversationid": "19:grouproom@thread.skype",
          "from": "19:grouproom@thread.skype",
          "properties": null,
          "amsreferences": []
        },
        {
          "id": "301",
          "displayName": "Bob",
          "originalarrivaltime": "2025-03-19T13:00:00.000Z",
          "messagetype": "RichText",
          "version": 1,
          "content": "hello everyone",
          "conversationid": "19:grouproom@thread.skype",
          "from": "8:bob",
          "properties": null,
          "amsreferences": []
        }
      ]
    },
    {
      "id": "8:empty",
      "displayName": "Empty Chat",
      "properties": {},
      "threadProperties": null,
      "MessageList": []
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_loader.py`:

```python
from datetime import timezone
from pathlib import Path

from skype_log_viewer.loader import load_export

FIXTURE = Path(__file__).parent / "fixtures" / "sample_export.json"


def test_load_basic_shape():
    data = load_export(FIXTURE)
    assert data.user_id == "8:me"
    # 3 conversations parsed (including the empty one)
    assert len(data.conversations) == 3


def test_conversations_sorted_alphabetically():
    data = load_export(FIXTURE)
    names = [c.display_name for c in data.conversations]
    assert names == sorted(names, key=str.casefold)


def test_messages_sorted_chronologically():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    assert [m.clean_text for m in alice.messages] == ["first message", "second message"]


def test_own_message_labeled_you():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    first = alice.messages[0]
    assert first.sender_id == "8:me"
    assert first.sender_name == "You"


def test_other_message_uses_display_name():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    assert alice.messages[1].sender_name == "Alice"


def test_timestamps_are_utc_aware():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    ts = alice.messages[0].timestamp
    assert ts.tzinfo is not None
    assert ts.utcoffset() == timezone.utc.utcoffset(None)


def test_group_detection_and_member_count():
    data = load_export(FIXTURE)
    group = next(c for c in data.conversations if c.id == "19:grouproom@thread.skype")
    assert group.is_group is True
    assert group.member_count == 8


def test_one_to_one_member_count_defaults_to_two():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    assert alice.is_group is False
    assert alice.member_count == 2


def test_system_event_cleaned_and_flagged():
    data = load_export(FIXTURE)
    group = next(c for c in data.conversations if c.id == "19:grouproom@thread.skype")
    event = group.messages[0]
    assert event.is_system is True
    assert event.clean_text == "[Alice added Bob]"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.loader'`

- [ ] **Step 4: Write the implementation**

Create `skype_log_viewer/loader.py`:

```python
from __future__ import annotations

import json
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
        is_group = "@thread.skype" in conv_id
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_loader.py -v`
Expected: PASS (9 passed)

- [ ] **Step 6: Commit**

```bash
git add skype_log_viewer/loader.py tests/test_loader.py tests/fixtures/sample_export.json
git commit -m "feat: parse Skype export into model"
```

---

## Task 7: Loader cache (`loader.py` — caching layer)

**Files:**
- Modify: `skype_log_viewer/loader.py` (add caching functions)
- Test: `tests/test_loader.py` (add cache tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loader.py`:

```python
def test_cache_round_trip(tmp_path):
    from skype_log_viewer.loader import load_with_cache

    cache_dir = tmp_path / "cache"
    first = load_with_cache(FIXTURE, cache_dir)
    # a cache file should now exist
    assert any(cache_dir.glob("*.pickle"))
    second = load_with_cache(FIXTURE, cache_dir)
    assert second.user_id == first.user_id
    assert len(second.conversations) == len(first.conversations)


def test_corrupt_cache_falls_back_to_parse(tmp_path):
    from skype_log_viewer.loader import load_with_cache, _cache_path

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    bad = _cache_path(FIXTURE, cache_dir)
    bad.write_bytes(b"not a pickle")
    data = load_with_cache(FIXTURE, cache_dir)
    assert data.user_id == "8:me"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_loader.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_with_cache'`

- [ ] **Step 3: Add the caching implementation**

Add these imports and functions to `skype_log_viewer/loader.py`. Add `import hashlib` and `import pickle` to the top imports, then append:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_loader.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/loader.py tests/test_loader.py
git commit -m "feat: add pickle cache for parsed exports"
```

---

## Task 8: Config & position persistence (`config.py`)

**Files:**
- Create: `skype_log_viewer/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
from skype_log_viewer.config import Config


def test_defaults(tmp_path):
    cfg = Config(tmp_path / "config.json")
    assert cfg.last_file is None
    assert cfg.recent_files == []
    assert cfg.show_system is False
    assert cfg.show_empty is False
    assert cfg.get_position("8:alice") is None


def test_set_and_persist(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(path)
    cfg.last_file = "C:/data/messages.json"
    cfg.add_recent("C:/data/messages.json")
    cfg.show_system = True
    cfg.set_position("8:alice", 42)
    cfg.save()

    reloaded = Config(path)
    assert reloaded.last_file == "C:/data/messages.json"
    assert reloaded.recent_files == ["C:/data/messages.json"]
    assert reloaded.show_system is True
    assert reloaded.get_position("8:alice") == 42


def test_recent_files_dedup_and_cap(tmp_path):
    cfg = Config(tmp_path / "config.json")
    for i in range(12):
        cfg.add_recent(f"file{i}.json")
    cfg.add_recent("file0.json")  # re-adding moves it to front
    assert cfg.recent_files[0] == "file0.json"
    assert len(cfg.recent_files) <= 10
    # no duplicates
    assert len(set(cfg.recent_files)) == len(cfg.recent_files)


def test_corrupt_config_uses_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("not json", encoding="utf-8")
    cfg = Config(path)
    assert cfg.last_file is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.config'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/config.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "SkypeLogViewer"
MAX_RECENT = 10


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = config_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


_DEFAULTS = {
    "last_file": None,
    "recent_files": [],
    "show_system": False,
    "show_empty": False,
    "positions": {},  # conversation id -> message index
}


class Config:
    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path) if path else (config_dir() / "config.json")
        self.data = dict(_DEFAULTS)
        self.data["recent_files"] = []
        self.data["positions"] = {}
        self.load()

    def load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                merged = dict(_DEFAULTS)
                merged["recent_files"] = []
                merged["positions"] = {}
                merged.update(loaded)
                self.data = merged
        except Exception:
            pass  # missing or corrupt -> keep defaults

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    # --- typed accessors ---
    @property
    def last_file(self) -> Optional[str]:
        return self.data.get("last_file")

    @last_file.setter
    def last_file(self, value: Optional[str]) -> None:
        self.data["last_file"] = value

    @property
    def recent_files(self) -> list[str]:
        return self.data.get("recent_files", [])

    @property
    def show_system(self) -> bool:
        return bool(self.data.get("show_system", False))

    @show_system.setter
    def show_system(self, value: bool) -> None:
        self.data["show_system"] = bool(value)

    @property
    def show_empty(self) -> bool:
        return bool(self.data.get("show_empty", False))

    @show_empty.setter
    def show_empty(self, value: bool) -> None:
        self.data["show_empty"] = bool(value)

    def add_recent(self, file_path: str) -> None:
        recent = [f for f in self.recent_files if f != file_path]
        recent.insert(0, file_path)
        self.data["recent_files"] = recent[:MAX_RECENT]

    def get_position(self, conv_id: str) -> Optional[int]:
        value = self.data.get("positions", {}).get(conv_id)
        return int(value) if value is not None else None

    def set_position(self, conv_id: str, index: int) -> None:
        self.data.setdefault("positions", {})[conv_id] = int(index)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/config.py tests/test_config.py
git commit -m "feat: add config and per-conversation position persistence"
```

---

## Task 9: Search (`search.py`)

**Files:**
- Create: `skype_log_viewer/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_search.py`:

```python
from skype_log_viewer.search import filter_indices, matching_indices, next_index

ITEMS = ["hello world", "goodbye", "Hello again", "nothing"]


def test_filter_indices_empty_query_returns_all():
    assert filter_indices(ITEMS, "") == [0, 1, 2, 3]


def test_filter_indices_case_insensitive():
    assert filter_indices(ITEMS, "hello") == [0, 2]


def test_matching_indices_empty_query_returns_none():
    assert matching_indices(ITEMS, "") == []


def test_matching_indices_finds_substrings():
    assert matching_indices(ITEMS, "o") == [0, 1, 3]


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.search'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/search.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_search.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add skype_log_viewer/search.py tests/test_search.py
git commit -m "feat: add filter and find-next search helpers"
```

---

## Task 10: Dialogs (`ui/info_dialog.py`, `ui/shortcuts_dialog.py`)

These are simple, self-contained dialogs. They are constructed in tests headlessly (a `wx.App` plus the dialog object, without `ShowModal`).

**Files:**
- Create: `skype_log_viewer/ui/info_dialog.py`
- Create: `skype_log_viewer/ui/shortcuts_dialog.py`
- Test: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ui_smoke.py`:

```python
import datetime

import pytest

wx = pytest.importorskip("wx")

from skype_log_viewer.model import Conversation, Message
from skype_log_viewer.ui.info_dialog import build_info_text
from skype_log_viewer.ui.shortcuts_dialog import SHORTCUTS_TEXT


def _conv():
    msgs = [
        Message("1", "8:me", "You",
                datetime.datetime(2025, 3, 18, 10, 0, tzinfo=datetime.timezone.utc),
                "RichText", "first", False),
        Message("2", "8:a", "Alice",
                datetime.datetime(2025, 3, 19, 21, 18, tzinfo=datetime.timezone.utc),
                "RichText", "second", False),
    ]
    return Conversation("8:a", "Alice", False, 2, msgs)


def test_build_info_text_contains_key_facts():
    text = build_info_text(_conv())
    assert "Alice" in text
    assert "2" in text          # total messages
    assert "Members" in text


def test_build_info_text_handles_empty_conversation():
    conv = Conversation("8:x", "Empty", False, 2, [])
    text = build_info_text(conv)
    assert "0" in text          # message count
    assert "Empty" in text


def test_shortcuts_text_lists_core_keys():
    for key in ("F6", "Ctrl+F", "Ctrl+L", "Ctrl+I", "Ctrl+E", "Ctrl+C", "F1"):
        assert key in SHORTCUTS_TEXT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.ui.info_dialog'`

- [ ] **Step 3: Write `ui/info_dialog.py`**

Create `skype_log_viewer/ui/info_dialog.py`:

```python
from __future__ import annotations

import wx

from ..formatting import format_timestamp
from ..model import Conversation


def build_info_text(conv: Conversation) -> str:
    """Plain-text accessible summary of a conversation."""
    lines = [
        f"Name: {conv.display_name}",
        f"Type: {'Group chat' if conv.is_group else 'One-on-one chat'}",
        f"Members: {conv.member_count}",
        f"Total messages: {conv.message_count}",
    ]
    if conv.messages:
        first = format_timestamp(conv.messages[0].timestamp)
        last = format_timestamp(conv.messages[-1].timestamp)
        lines.append(f"First message: {first}")
        lines.append(f"Last message: {last}")
    return "\n".join(lines)


class InfoDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, conv: Conversation) -> None:
        super().__init__(parent, title="Conversation info",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        text = wx.TextCtrl(self, value=build_info_text(conv),
                           style=wx.TE_MULTILINE | wx.TE_READONLY)
        text.SetName("Conversation info")
        sizer.Add(text, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.SetSize((420, 280))
        text.SetFocus()
```

- [ ] **Step 4: Write `ui/shortcuts_dialog.py`**

Create `skype_log_viewer/ui/shortcuts_dialog.py`:

```python
from __future__ import annotations

import wx

SHORTCUTS_TEXT = """Keyboard shortcuts

F6 / Shift+F6   Move between panes (conversations, search, messages, detail)
Tab / Shift+Tab Move between controls and menus
Up / Down       Move within the focused list
Home / End      Jump to start / end of the list
Enter           From conversations: move focus into the message list
Ctrl+F          Find within the conversation (Enter = next, Shift+Enter = previous)
Ctrl+L          Filter the message list to matches (Esc clears)
Esc             Clear the current search
Ctrl+C          Copy the selected message's full text
Ctrl+I          Show conversation info
Ctrl+E          Show or hide system events (joins, leaves, topic changes)
Ctrl+O          Open a different export file
F1              Show this list of shortcuts
"""


class ShortcutsDialog(wx.Dialog):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, title="Keyboard shortcuts",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        text = wx.TextCtrl(self, value=SHORTCUTS_TEXT,
                           style=wx.TE_MULTILINE | wx.TE_READONLY)
        text.SetName("Keyboard shortcuts")
        sizer.Add(text, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.SetSize((520, 380))
        text.SetFocus()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_smoke.py -v`
Expected: PASS (3 passed). If wxPython cannot create a display, `pytest.importorskip` keeps it from failing CI; on the dev Windows machine it passes.

- [ ] **Step 6: Commit**

```bash
git add skype_log_viewer/ui/info_dialog.py skype_log_viewer/ui/shortcuts_dialog.py tests/test_ui_smoke.py
git commit -m "feat: add info and shortcuts dialogs"
```

---

## Task 11: Main window (`ui/main_frame.py`)

The main window wires the four panes, menus, and key handling onto the logic modules. GUI behavior is validated by a headless construction smoke test plus manual verification (Task 12).

**Files:**
- Create: `skype_log_viewer/ui/main_frame.py`
- Test: `tests/test_ui_smoke.py` (add a frame construction test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui_smoke.py`:

```python
def test_main_frame_builds_and_loads_conversation(tmp_path):
    from pathlib import Path
    from skype_log_viewer.loader import load_export
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    app = wx.App()
    fixture = Path(__file__).parent / "fixtures" / "sample_export.json"
    data = load_export(fixture)
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)

    # conversation list excludes the empty conversation by default
    assert frame.conv_list.GetCount() == 2

    # selecting the first conversation populates the virtual message list
    frame.select_conversation(0)
    assert frame.msg_list.GetItemCount() >= 1

    frame.Destroy()
    app.Destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_smoke.py::test_main_frame_builds_and_loads_conversation -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skype_log_viewer.ui.main_frame'`

- [ ] **Step 3: Write the implementation**

Create `skype_log_viewer/ui/main_frame.py`:

```python
from __future__ import annotations

from typing import Optional

import wx

from ..config import Config
from ..formatting import date_label, format_row, make_preview, to_local
from ..model import Conversation, ExportData, Message
from ..search import filter_indices, matching_indices, next_index
from .info_dialog import InfoDialog
from .shortcuts_dialog import ShortcutsDialog

# Menu / accelerator command ids
ID_SHOW_SYSTEM = wx.NewIdRef()
ID_SHOW_EMPTY = wx.NewIdRef()
ID_FIND = wx.NewIdRef()
ID_FILTER = wx.NewIdRef()
ID_INFO = wx.NewIdRef()
ID_COPY_MSG = wx.NewIdRef()
ID_SHORTCUTS = wx.NewIdRef()


class _Row:
    """A row in the message list: either a date separator or a message."""

    __slots__ = ("text", "message")

    def __init__(self, text: str, message: Optional[Message]) -> None:
        self.text = text
        self.message = message


class MainFrame(wx.Frame):
    def __init__(self, data: ExportData, config: Config) -> None:
        super().__init__(None, title="Skype Log Viewer", size=(1000, 700))
        self.data = data
        self.config = config
        self.current_conv: Optional[Conversation] = None
        self.rows: list[_Row] = []
        self.search_mode = "filter"  # or "find"

        self._build_menu()
        self._build_layout()
        self._bind_events()
        self.rebuild_conversation_list()
        self.CreateStatusBar()
        self.SetStatusText("Ready")

    # ---------- construction ----------
    def _build_menu(self) -> None:
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Open...\tCtrl+O")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit")
        menubar.Append(file_menu, "&File")

        view_menu = wx.Menu()
        self.mi_show_system = view_menu.AppendCheckItem(ID_SHOW_SYSTEM, "Show &system events\tCtrl+E")
        self.mi_show_empty = view_menu.AppendCheckItem(ID_SHOW_EMPTY, "Show &empty conversations")
        self.mi_show_system.Check(self.config.show_system)
        self.mi_show_empty.Check(self.config.show_empty)
        menubar.Append(view_menu, "&View")

        search_menu = wx.Menu()
        search_menu.Append(ID_FIND, "&Find...\tCtrl+F")
        search_menu.Append(ID_FILTER, "Fi&lter...\tCtrl+L")
        menubar.Append(search_menu, "&Search")

        conv_menu = wx.Menu()
        conv_menu.Append(ID_INFO, "Conversation &info\tCtrl+I")
        conv_menu.Append(ID_COPY_MSG, "&Copy message text\tCtrl+C")
        menubar.Append(conv_menu, "&Conversation")

        help_menu = wx.Menu()
        help_menu.Append(ID_SHORTCUTS, "&Keyboard shortcuts\tF1")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

    def _build_layout(self) -> None:
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.HORIZONTAL)

        # Left: conversation list
        left = wx.BoxSizer(wx.VERTICAL)
        left.Add(wx.StaticText(panel, label="Conversations"), 0, wx.ALL, 4)
        self.conv_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.conv_list.SetName("Conversations")
        left.Add(self.conv_list, 1, wx.EXPAND | wx.ALL, 4)
        root.Add(left, 1, wx.EXPAND)

        # Right: search + message list + detail
        right = wx.BoxSizer(wx.VERTICAL)
        right.Add(wx.StaticText(panel, label="Search"), 0, wx.ALL, 4)
        self.search_ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName("Search this conversation")
        right.Add(self.search_ctrl, 0, wx.EXPAND | wx.ALL, 4)

        right.Add(wx.StaticText(panel, label="Messages"), 0, wx.ALL, 4)
        self.msg_list = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER
        )
        self.msg_list.InsertColumn(0, "Message")
        self.msg_list.SetName("Messages")
        right.Add(self.msg_list, 3, wx.EXPAND | wx.ALL, 4)

        right.Add(wx.StaticText(panel, label="Selected message"), 0, wx.ALL, 4)
        self.detail = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.detail.SetName("Selected message text")
        right.Add(self.detail, 2, wx.EXPAND | wx.ALL, 4)

        root.Add(right, 2, wx.EXPAND)
        panel.SetSizer(root)
        self.panel = panel
        self._panes = [self.conv_list, self.search_ctrl, self.msg_list, self.detail]

    def _bind_events(self) -> None:
        self.Bind(wx.EVT_LISTBOX, self.on_conversation_selected, self.conv_list)
        self.msg_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_message_selected)
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search_text)
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search_enter)

        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.on_toggle_system, id=ID_SHOW_SYSTEM)
        self.Bind(wx.EVT_MENU, self.on_toggle_empty, id=ID_SHOW_EMPTY)
        self.Bind(wx.EVT_MENU, lambda e: self.focus_search("find"), id=ID_FIND)
        self.Bind(wx.EVT_MENU, lambda e: self.focus_search("filter"), id=ID_FILTER)
        self.Bind(wx.EVT_MENU, self.on_info, id=ID_INFO)
        self.Bind(wx.EVT_MENU, self.on_copy_message, id=ID_COPY_MSG)
        self.Bind(wx.EVT_MENU, self.on_shortcuts, id=ID_SHORTCUTS)

        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

    # ---------- conversation list ----------
    def visible_conversations(self) -> list[Conversation]:
        if self.config.show_empty:
            return list(self.data.conversations)
        return [c for c in self.data.conversations if c.message_count > 0]

    def rebuild_conversation_list(self) -> None:
        self._visible_convs = self.visible_conversations()
        self.conv_list.Set([c.display_name for c in self._visible_convs])

    def on_conversation_selected(self, event: wx.CommandEvent) -> None:
        self.select_conversation(self.conv_list.GetSelection())

    def select_conversation(self, index: int) -> None:
        if index is None or index < 0 or index >= len(self._visible_convs):
            return
        if self.conv_list.GetSelection() != index:
            self.conv_list.SetSelection(index)
        self.current_conv = self._visible_convs[index]
        self.search_ctrl.ChangeValue("")
        self.rebuild_rows()
        restored = self.config.get_position(self.current_conv.id)
        target = restored if restored is not None and restored < len(self.rows) else 0
        self._select_row(target)
        self.SetStatusText(
            f"{self.current_conv.display_name} — "
            f"{self.current_conv.member_count} members, "
            f"{self.current_conv.message_count} messages"
        )

    # ---------- message rows ----------
    def working_messages(self) -> list[Message]:
        if not self.current_conv:
            return []
        if self.config.show_system:
            return list(self.current_conv.messages)
        return [m for m in self.current_conv.messages if not m.is_system]

    def rebuild_rows(self, filter_query: str = "") -> None:
        messages = self.working_messages()
        if filter_query:
            keep = set(filter_indices(messages, filter_query, key=lambda m: m.clean_text))
            messages = [m for i, m in enumerate(messages) if i in keep]

        rows: list[_Row] = []
        last_day = None
        for m in messages:
            local = to_local(m.timestamp)
            day = local.date()
            if day != last_day:
                rows.append(_Row(f"— {date_label(m.timestamp)} —", None))
                last_day = day
            preview = make_preview(m.clean_text)
            rows.append(_Row(format_row(m.sender_name, local, preview), m))
        self.rows = rows
        self.msg_list.SetItemCount(len(rows))
        self.msg_list.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # wx virtual-list callback
        if 0 <= item < len(self.rows):
            return self.rows[item].text
        return ""

    def _select_row(self, row_index: int) -> None:
        if not self.rows:
            self.detail.ChangeValue("")
            return
        row_index = max(0, min(row_index, len(self.rows) - 1))
        self.msg_list.Select(row_index)
        self.msg_list.Focus(row_index)
        self.msg_list.EnsureVisible(row_index)
        self._update_detail(row_index)

    def on_message_selected(self, event: wx.ListEvent) -> None:
        self._update_detail(event.GetIndex())

    def _update_detail(self, row_index: int) -> None:
        if 0 <= row_index < len(self.rows):
            row = self.rows[row_index]
            self.detail.ChangeValue(row.message.clean_text if row.message else row.text)
            if self.current_conv:
                self.config.set_position(self.current_conv.id, row_index)

    # ---------- search ----------
    def focus_search(self, mode: str) -> None:
        self.search_mode = mode
        self.search_ctrl.SetFocus()
        self.search_ctrl.SelectAll()

    def on_search_text(self, event: wx.CommandEvent) -> None:
        if self.search_mode == "filter":
            self.rebuild_rows(self.search_ctrl.GetValue())
            self._select_row(0)

    def on_search_enter(self, event: wx.CommandEvent) -> None:
        if self.search_mode != "find":
            return
        query = self.search_ctrl.GetValue()
        msg_rows = [(i, r) for i, r in enumerate(self.rows) if r.message]
        texts = [r.message.clean_text for _, r in msg_rows]
        local_matches = matching_indices(texts, query)
        if not local_matches:
            self.SetStatusText(f'No matches for "{query}"')
            return
        row_matches = [msg_rows[i][0] for i in local_matches]
        current = self.msg_list.GetFirstSelected()
        forward = not wx.GetKeyState(wx.WXK_SHIFT)
        target = next_index(row_matches, current, forward=forward)
        if target is not None:
            self.msg_list.SetFocus()
            self._select_row(target)
            position = row_matches.index(target) + 1
            self.SetStatusText(f"Match {position} of {len(row_matches)}")

    # ---------- menu handlers ----------
    def on_toggle_system(self, event: wx.CommandEvent) -> None:
        self.config.show_system = self.mi_show_system.IsChecked()
        self.rebuild_rows(self.search_ctrl.GetValue() if self.search_mode == "filter" else "")
        self._select_row(0)

    def on_toggle_empty(self, event: wx.CommandEvent) -> None:
        self.config.show_empty = self.mi_show_empty.IsChecked()
        self.rebuild_conversation_list()

    def on_info(self, event: wx.CommandEvent) -> None:
        if self.current_conv:
            dlg = InfoDialog(self, self.current_conv)
            dlg.ShowModal()
            dlg.Destroy()

    def on_copy_message(self, event: wx.CommandEvent) -> None:
        row_index = self.msg_list.GetFirstSelected()
        if 0 <= row_index < len(self.rows) and self.rows[row_index].message:
            text = self.rows[row_index].message.clean_text
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(text))
                wx.TheClipboard.Close()
                self.SetStatusText("Message copied to clipboard")

    def on_shortcuts(self, event: wx.CommandEvent) -> None:
        dlg = ShortcutsDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def on_open(self, event: wx.CommandEvent) -> None:
        with wx.FileDialog(
            self, "Open Skype export", wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._load_path(dlg.GetPath())

    def _load_path(self, path: str) -> None:
        from ..loader import load_with_cache
        from ..config import cache_dir
        try:
            self.data = load_with_cache(path, cache_dir())
        except Exception as exc:
            wx.MessageBox(f"Could not open this file:\n{exc}", "Open failed",
                          wx.OK | wx.ICON_ERROR)
            return
        self.config.last_file = path
        self.config.add_recent(path)
        self.config.save()
        self.current_conv = None
        self.detail.ChangeValue("")
        self.rebuild_conversation_list()

    # ---------- key handling ----------
    def on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        if key == wx.WXK_F6:
            self._cycle_pane(forward=not event.ShiftDown())
            return
        if key == wx.WXK_ESCAPE and self.search_ctrl.GetValue():
            self.search_ctrl.ChangeValue("")
            self.rebuild_rows("")
            self._select_row(0)
            return
        event.Skip()

    def _cycle_pane(self, forward: bool) -> None:
        focused = wx.Window.FindFocus()
        try:
            idx = self._panes.index(focused)
        except ValueError:
            idx = -1
        step = 1 if forward else -1
        self._panes[(idx + step) % len(self._panes)].SetFocus()

    def on_close(self, event: wx.CloseEvent) -> None:
        self.config.save()
        event.Skip()
```

Note: `OnGetItemText` is the wx virtual `wx.ListCtrl` callback (wx looks it up by that exact name on the control's parent only when the list is created with the frame as the owner via `SetItemCount`; here the list is a child, so wire it explicitly in Step 4 below).

- [ ] **Step 4: Wire the virtual-list callback**

Because `wx.ListCtrl` calls `OnGetItemText` on the **list control**, not the frame, subclass the list inline. Replace the `self.msg_list = wx.ListCtrl(...)` line in `_build_layout` with a tiny virtual-list subclass that delegates to the frame. Add this class at the top of the file (after the imports):

```python
class _VirtualMessageList(wx.ListCtrl):
    def __init__(self, parent: wx.Window, owner: "MainFrame") -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self._owner = owner

    def OnGetItemText(self, item: int, column: int) -> str:
        return self._owner.OnGetItemText(item, column)
```

And change the construction in `_build_layout` to:

```python
        self.msg_list = _VirtualMessageList(panel, self)
        self.msg_list.InsertColumn(0, "Message")
        self.msg_list.SetName("Messages")
```

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `uv run pytest tests/test_ui_smoke.py -v`
Expected: PASS (all UI smoke tests pass)

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS (all tests across all modules pass)

- [ ] **Step 7: Commit**

```bash
git add skype_log_viewer/ui/main_frame.py tests/test_ui_smoke.py
git commit -m "feat: add main window with panes, search, and key handling"
```

---

## Task 12: App entry point, startup, and README

**Files:**
- Create: `skype_log_viewer/__main__.py`
- Create: `README.md`

- [ ] **Step 1: Write `__main__.py`**

Create `skype_log_viewer/__main__.py`:

```python
from __future__ import annotations

import os

import wx

from .config import Config, cache_dir
from .loader import load_with_cache
from .model import ExportData
from .ui.main_frame import MainFrame


def _initial_data(config: Config) -> tuple[ExportData, bool]:
    """Load the last-used file if it still exists. Returns (data, loaded_ok)."""
    if config.last_file and os.path.exists(config.last_file):
        try:
            return load_with_cache(config.last_file, cache_dir()), True
        except Exception:
            pass
    return ExportData(user_id="", conversations=[]), False


def main() -> None:
    app = wx.App()
    config = Config()
    data, loaded = _initial_data(config)
    frame = MainFrame(data, config)
    frame.Bind(wx.EVT_CLOSE, frame.on_close)
    frame.Show()

    if not loaded:
        wx.CallAfter(_prompt_for_file, frame)

    app.MainLoop()


def _prompt_for_file(frame: MainFrame) -> None:
    with wx.FileDialog(
        frame, "Open your Skype messages.json export",
        wildcard="JSON files (*.json)|*.json",
        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
    ) as dlg:
        if dlg.ShowModal() == wx.ID_OK:
            frame._load_path(dlg.GetPath())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `README.md`**

Create `README.md`:

```markdown
# Skype Log Viewer

An accessible desktop viewer for exported Skype chat logs (`messages.json`),
built with Python and wxPython. Keyboard-driven and screen-reader friendly.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

```
uv sync
```

## Run

```
uv run python -m skype_log_viewer
```

On first launch you'll be asked to pick your `messages.json` export. The file is
parsed once and cached, so later launches of the same file are near-instant.

## Keyboard shortcuts

Press **F1** in the app for the full list. Highlights:

- **F6 / Shift+F6** — move between the four panes
- **Ctrl+F** — find within the conversation (Enter = next, Shift+Enter = previous)
- **Ctrl+L** — filter the message list to matches (Esc clears)
- **Ctrl+C** — copy the selected message's full text
- **Ctrl+I** — conversation info
- **Ctrl+E** — show/hide system events
- **Ctrl+O** — open a different export

## Tests

```
uv run pytest
```
```

- [ ] **Step 3: Manual verification**

Run: `uv run python -m skype_log_viewer`
When prompted, choose the reference export:
`\\epicmedia\personal_folder\Private archive\skype export\messages.json`

Verify by keyboard + screen reader:
- The conversation list reads conversation names; arrowing announces each.
- Selecting a conversation populates the message list; arrowing announces "sender, time: preview" and date-separator rows.
- The detail field reads the full selected message.
- Ctrl+F then a term + Enter jumps match-to-match; status shows "Match X of Y".
- Ctrl+L filters; Esc restores.
- Ctrl+E toggles system events; Ctrl+I shows info; Ctrl+C copies; F1 lists shortcuts.
- Close and relaunch: it reopens the same file and returns to the last conversation/position.

- [ ] **Step 4: Commit**

```bash
git add skype_log_viewer/__main__.py README.md
git commit -m "feat: add app entry point, startup file handling, and README"
```

---

## Self-Review (completed during plan authoring)

**Spec coverage check (each spec section → task):**
- §1 Tech (Python 3.13, wxPython, uv) → Task 1
- §2 Layout & four-pane focus order → Task 11 (`_build_layout`, `_panes`)
- §3 Keyboard scheme (F6, Ctrl+F/L/I/E/C, F1, Esc, type-ahead) → Task 11 (`on_char_hook`, menu accelerators) + Task 10 (shortcuts text)
- §4 Data model & loading + cache + last-file + hide empty → Tasks 2, 6, 7, 8, 12
- §5 Name resolution ("You", group fallback) → Tasks 5, 6
- §6 Text cleaning (emoticon, mention, link, quote, media, call, system) → Task 4
- §7 Message list (virtual list, sender+time+256 preview, date separators, local 12h) → Tasks 3, 11
- §8 In-conversation search (filter + find-next/prev, count) → Tasks 9, 11
- §9 Extras (copy, info, remember position) → Tasks 8, 10, 11
- §10 Error handling (bad file, corrupt cache) → Tasks 7, 11 (`on_open`/`_load_path`), 12
- §11 Project structure & testing → all tasks (pytest-first for logic; smoke for UI)
- §12 Out of scope → not implemented (correct)

**Placeholder scan:** none — every code/test step contains complete content.

**Type consistency:** `Message`/`Conversation`/`ExportData` fields are used identically across loader, search, UI, and dialogs. `clean_content(content, msgtype, name_lookup=)`, `filter_indices`/`matching_indices`/`next_index`, `format_row`/`date_label`/`to_local`/`make_preview`, and `Config` accessors match their definitions at every call site.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-31-skype-log-viewer.md`.
