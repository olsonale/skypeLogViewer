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
