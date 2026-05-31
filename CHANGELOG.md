# Changelog

## Unreleased

### Fixed
- **Conversations with only system events are now hidden by default.** The
  conversation list previously counted join/leave, member-add and topic-change
  events as messages, so chats that "did not actually contain messages" — such
  as single-participant groups with no stored events — still cluttered the list.
  They are now treated as empty and hidden unless *View ▸ Show empty
  conversations* is enabled. ([#1](https://github.com/olsonale/skypeLogViewer/issues/1))

## 0.2.0 — 2026-05-31

### Added
- **Jump through a conversation by time.** In the message list you can now move
  in larger steps and land on a date heading so your screen reader announces the
  new date:
  - **Shift+Up / Shift+Down** — previous / next day
  - **Ctrl+Up / Ctrl+Down** — previous / next calendar month
  - **Page Up / Page Down** — previous / next calendar year

  Jumping forward skips over empty months and years, and "previous" first moves
  to the start of the current period before stepping back. At the first or last
  entry you hear a beep and a status message instead of moving. These shortcuts
  are also listed in the keyboard help (F1).

### Changed
- **Message rows now read the sender and what they said before the time.** A row
  that used to be announced as "You, Mar 19, 2025, 3:14 PM: hey there" is now
  read as "You: hey there, Mar 19, 2025, 3:14 PM", so you hear who spoke and the
  message up front, with the timestamp at the end.
- **Longer message previews in the list.** Rows now show up to 2048 characters of
  a message before truncating (previously 256), so you can read more without
  opening the detail pane.

### Fixed
- Fixed a crash that could occur when searching past the last match.
