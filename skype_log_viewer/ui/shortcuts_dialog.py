from __future__ import annotations

import wx

SHORTCUTS_TEXT = """Keyboard shortcuts

F6 / Shift+F6   Move between panes (conversations, search, scope, messages, detail)
Tab / Shift+Tab Move between controls and menus
Up / Down       Move within the focused list
Home / End      Jump to start / end of the list
Shift+Up / Down Jump to previous / next day (in the message list)
Ctrl+Up / Down  Jump to previous / next calendar month (in the message list)
Page Up / Down  Jump to previous / next calendar year (in the message list)
Enter           From conversations: move focus into the message list
Ctrl+F          Find within the conversation (Enter = next, Shift+Enter = previous)
Ctrl+L          Filter the message list to matches (Esc clears)
Search scope    Choose This conversation or All conversations (below the search box)
                With All conversations, press Enter to search every conversation;
                Enter on a result jumps to that message; Esc returns to normal.
Esc             Clear the current search or leave the global results list
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
