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


class _VirtualMessageList(wx.ListCtrl):
    def __init__(self, parent: wx.Window, owner: "MainFrame") -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self._owner = owner

    def OnGetItemText(self, item: int, column: int) -> str:
        return self._owner.OnGetItemText(item, column)


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
        self.msg_list = _VirtualMessageList(panel, self)
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
