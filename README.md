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
