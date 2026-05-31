# Skype Log Viewer — Design

**Date:** 2026-05-31
**Status:** Approved (design); pending implementation plan

## 1. Summary & technology

A keyboard-driven, screen-reader-friendly **desktop application** for re-reading exported
Skype logs. Primary use: reading one-on-one chats, with fast search *inside* a conversation.

- **Language/runtime:** Python 3.13
- **GUI toolkit:** wxPython 4.2 (wraps native Windows controls, which report to screen
  readers such as NVDA and JAWS via MSAA/UIA)
- **Dependency management:** **uv** for everything — a `pyproject.toml` managed by uv,
  dependencies added with `uv add`, the app and tests run via `uv run`. No bare
  `pip`/`requirements.txt`.
- **Input data:** a Skype `messages.json` export. Reference export for development:
  `\\epicmedia\personal_folder\Private archive\skype export\messages.json`
  (~77 MB, 245 conversations, ~180,808 messages; largest single conversation has
  121,572 messages; many conversations are empty).

The app parses the export once and caches the processed result so later launches are
near-instant.

## 2. Window layout & focus order

A single main window with a menu bar and four focusable panes, reached in this
`Tab` / `F6` order:

1. **Conversation list** (left) — all non-empty conversations, sorted A–Z.
2. **Search box** (top of the right side) — filters or finds within the selected conversation.
3. **Message list** (right, main area) — messages of the selected conversation, with date
   separators.
4. **Message detail field** (bottom) — a read-only multi-line text box holding the **full
   text of the currently selected message**, read with the screen-reader cursor.

`F6` / `Shift+F6` cycle forward/back between the four panes; `Tab` also moves through them
and the menus. Every control carries an explicit accessible label/name so the screen reader
announces what it is and the current context.

## 3. Keyboard scheme

- **Conversation list:** arrows to move; type-ahead jumps to a name by first letters;
  `Enter` moves focus into the message list.
- **Message list:** arrows / `PageUp`–`PageDown` / `Home`–`End` to move; selecting a message
  fills the detail field. Date-separator rows are selectable and announce the date.
- **Detail field:** screen reader reads by line/word/character; `Ctrl+C` copies the whole
  message text.
- **Search:** `Ctrl+F` focuses the search box; `Enter` = find-next, `Shift+Enter` =
  find-previous, announcing "match 2 of 9"; `Ctrl+L` toggles **filter mode** (list shrinks to
  matches); `Esc` clears search and restores the full list.
- **Copy:** `Ctrl+C` copies the selected message's full text from anywhere.
- **Conversation info:** `Ctrl+I` opens an accessible summary dialog.
- **Toggle system events:** `Ctrl+E` shows/hides join/leave/topic events.
- **Shortcuts help:** `F1` opens a dialog listing every shortcut, top to bottom.

## 4. Data model & loading

- On open, the app reads the JSON and builds in-memory **Conversation** and **Message**
  objects.
- It writes a **cache** keyed to the source file's path + size + modified-time. Reopening an
  unchanged file loads the cache instead of re-parsing. Corrupt cache falls back to a fresh
  parse.
- **File source:** the last-used export opens automatically on startup; `File ▸ Open` and a
  Recent list switch exports. Config and cache live under `%APPDATA%\SkypeLogViewer\`.
- **Empty conversations** are hidden by default; `View ▸ Show empty conversations` reveals
  them.

## 5. Name resolution

- **One-on-one chat:** the other person is shown by their display name (from the
  conversation/export); the user's own messages are labeled **"You"** (own messages =
  `from` equals the export's `userId`, e.g. `8:power-up77`).
- **Group chat:** each sender uses the display name carried on the message
  (`displayName`, present on ~81% of messages), falling back to a cleaned Skype ID when
  absent. A name map is built by scanning message `displayName` values and
  `threadProperties.members`.

## 6. Message rendering (text cleaning)

Raw `content` is HTML. Convert to clean, speech-friendly text using the Python standard
library (`html.parser`, `html` entity decoding, regex) — no heavy dependencies:

- Strip tags, decode entities, keep `@mention` display names and link text (URL kept in
  parentheses).
- `<quote>` → `Quote from <name>: "<text>"`.
- **Media → labels:** `[Photo]`, `[Voice message]`, `[File: <name>]`, `[Video]`,
  `[Poll: <title>]` (from `RichText/UriObject`, `Media_AudioMsg`, `Media_GenericFile`,
  `Media_Video`, `Poll`).
- **Calls** (`Event/Call`) → `[Call, 4 seconds]` / `[Call ended]`.
- **System events** (`ThreadActivity/*`: AddMember, DeleteMember, TopicUpdate, RoleUpdate,
  etc.) → bracketed labels (e.g. `[Maria joined the chat]`), **hidden by default** per the
  toggle in §3.

## 7. Message list specifics

- A **virtual list control** (`wx.ListCtrl` in `LC_VIRTUAL` mode) to handle the 121k-message
  conversation without lag while remaining natively accessible.
- Each row announces **sender + local 12-hour time + preview**, with the preview truncated
  to **256 characters**. Example: `You, Mar 19, 2025, 3:14 PM: Hey, are you free tomorrow…`
- **Date separators** appear as their own rows — `— Wednesday, March 19, 2025 —` — whenever
  the calendar day changes. They are skipped by find/filter navigation but selectable.
- Timestamps (`originalarrivaltime`, stored in UTC) are converted to the user's **local
  12-hour** time for both list rows and the info dialog.

## 8. Search within a conversation

Both modes, over the cleaned message text, case-insensitive substring matching:

- **Filter** (`Ctrl+L`): list shows only matching messages; `Esc` restores the full list.
- **Find next/previous** (`Ctrl+F`, then `Enter` / `Shift+Enter`): jumps match-to-match in
  the full list and announces position and count ("match 2 of 9").

Global cross-conversation search is explicitly **out of scope** for this version (§12).

## 9. Extras

- **Copy message text** — `Ctrl+C` copies the selected message's full text to the clipboard.
- **Conversation info** (`Ctrl+I`) — accessible dialog: name, member count, total messages,
  and date range (first/last message, local time).
- **Remember position** — the per-conversation last-selected message index is saved in config
  and restored when that conversation is reopened; relaunching the app returns to the last
  conversation as well.

## 10. Error handling

Friendly, screen-reader-announced messages (accessible dialogs) for: file not found / moved,
malformed or non-Skype JSON, and cache corruption (falls back to a fresh parse). The app
never fails silently; every error surfaces a clear, readable message.

## 11. Project structure & testing

A small Python package managed by uv:

```
skypeLogViewer/
  pyproject.toml            # uv-managed; deps: wxPython, pytest (dev)
  skype_log_viewer/
    __init__.py
    __main__.py             # entry point: `uv run python -m skype_log_viewer`
    model.py                # Conversation, Message dataclasses
    loader.py               # JSON parse + cache load/save
    textclean.py            # HTML→text, media/call/event labels
    names.py                # name resolution / "You" labeling
    search.py               # filter + find-next/previous logic
    config.py               # config + per-conversation position persistence
    ui/
      main_frame.py         # main window, panes, menu, focus order
      shortcuts_dialog.py   # F1 shortcuts list
      info_dialog.py        # Ctrl+I conversation info
  tests/
  README.md
```

**Testing:** the non-GUI logic is built **test-first with pytest**, using small fixtures
sampled from the real export. Coverage targets: text cleaning per message type, name
resolution, search/filter behavior, UTC→local time conversion, and cache round-trips. A light
GUI smoke test confirms the main window builds. Tests run via `uv run pytest`.

## 12. Out of scope (this version)

- Global cross-conversation search
- Exporting conversations to files
- Editing / replying / sending
- Downloading the remote media behind `[Photo]` / `[File]` placeholders (the export stores
  only links/IDs, not the binaries)
- Statistics / analytics
