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


def test_system_only_conversation_hidden_by_default(tmp_path):
    from skype_log_viewer.model import ExportData
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    system_only = Conversation(
        "19:lonely@thread.skype", "Lonely Group", True, 1,
        [Message("9", "19:lonely@thread.skype", "Bob",
                 datetime.datetime(2025, 3, 19, 12, 0, tzinfo=datetime.timezone.utc),
                 "ThreadActivity/AddMember", "", True)],
    )
    data = ExportData(user_id="8:me", conversations=[_conv(), system_only])

    app = wx.App()
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)
    try:
        # a conversation with only system events does not "actually contain
        # messages", so it is hidden by default
        assert frame.conv_list.GetCount() == 1

        # ...but the "Show empty conversations" toggle reveals it
        frame.config.show_empty = True
        frame.rebuild_conversation_list()
        assert frame.conv_list.GetCount() == 2
    finally:
        frame.Destroy()
        app.Destroy()


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

    # selecting a conversation should populate the detail field with text
    assert frame.detail.GetValue() != ""

    frame.Destroy()
    app.Destroy()


def test_rebuild_rows_assigns_dates(tmp_path):
    from pathlib import Path
    from skype_log_viewer.formatting import to_local
    from skype_log_viewer.loader import load_export
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    app = wx.App()
    fixture = Path(__file__).parent / "fixtures" / "sample_export.json"
    data = load_export(fixture)
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)
    frame.select_conversation(0)  # "Alice" (conversations sort alphabetically)

    rows = frame.rows
    assert rows
    for row in rows:
        assert isinstance(row.date, datetime.date)
    # message rows carry their own local date
    for row in rows:
        if row.message is not None:
            assert row.date == to_local(row.message.timestamp).date()
    # each separator's date matches the row that follows it
    for i, row in enumerate(rows):
        if row.message is None:
            assert rows[i + 1].date == row.date

    frame.Destroy()
    app.Destroy()


def _frame_with_two_days(tmp_path):
    from pathlib import Path
    from skype_log_viewer.loader import load_export
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    fixture = Path(__file__).parent / "fixtures" / "sample_export.json"
    data = load_export(fixture)
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)
    frame.select_conversation(0)  # Alice: two messages ~35h apart => 2+ day blocks
    return frame


def test_time_jump_day_moves_between_separators(tmp_path):
    app = wx.App()
    frame = _frame_with_two_days(tmp_path)
    seps = [i for i, r in enumerate(frame.rows) if r.message is None]
    assert len(seps) >= 2

    frame._select_row(seps[0])
    frame._time_jump("day", 1)
    assert frame.msg_list.GetFirstSelected() == seps[1]

    # smart previous from the second day's separator -> previous day's separator
    frame._time_jump("day", -1)
    assert frame.msg_list.GetFirstSelected() == seps[0]

    frame.Destroy()
    app.Destroy()


def test_time_jump_at_boundary_does_not_move(tmp_path):
    app = wx.App()
    frame = _frame_with_two_days(tmp_path)
    seps = [i for i, r in enumerate(frame.rows) if r.message is None]

    frame._select_row(seps[0])
    frame._time_jump("day", -1)  # already at the first period -> boundary
    assert frame.msg_list.GetFirstSelected() == seps[0]
    assert "earlier day" in frame.GetStatusBar().GetStatusText().lower()

    frame.Destroy()
    app.Destroy()


def test_shortcuts_text_lists_time_jump_keys():
    from skype_log_viewer.ui.shortcuts_dialog import SHORTCUTS_TEXT
    for key in ("Shift+Up", "Ctrl+Up", "Page Up"):
        assert key in SHORTCUTS_TEXT


def _frame_with_multi(tmp_path):
    """Frame over one conversation spanning two Jan days, March, and Jul 2026.

    Timestamps are at noon UTC mid-month, so each message's local date stays in
    its intended month/year for any real timezone offset (±14h) — the month and
    year jumps are deterministic regardless of where the test runs.
    """
    from skype_log_viewer.model import ExportData
    from skype_log_viewer.config import Config
    from skype_log_viewer.ui.main_frame import MainFrame

    utc = datetime.timezone.utc
    stamps = [
        datetime.datetime(2025, 1, 15, 12, 0, tzinfo=utc),
        datetime.datetime(2025, 1, 20, 12, 0, tzinfo=utc),  # same month as above
        datetime.datetime(2025, 3, 15, 12, 0, tzinfo=utc),  # gap over February
        datetime.datetime(2026, 7, 15, 12, 0, tzinfo=utc),  # gap over rest of 2025
    ]
    msgs = [Message(str(i), "8:me", "You", dt, "RichText", f"m{i}", False)
            for i, dt in enumerate(stamps)]
    data = ExportData("8:me", [Conversation("8:multi", "Multi", False, 2, msgs)])
    cfg = Config(tmp_path / "config.json")
    frame = MainFrame(data, cfg)
    frame.select_conversation(0)
    return frame


def _separators(frame):
    return [i for i, r in enumerate(frame.rows) if r.message is None]


def test_time_jump_month_moves_between_months(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    by_month = {}
    for i in _separators(frame):
        key = (frame.rows[i].date.year, frame.rows[i].date.month)
        by_month.setdefault(key, i)  # earliest separator of each month
    jan, mar = by_month[(2025, 1)], by_month[(2025, 3)]

    frame._select_row(jan)
    frame._time_jump("month", 1)  # Jan -> Mar (skips empty Feb and the 2nd Jan day)
    assert frame.msg_list.GetFirstSelected() == mar

    # smart previous from March's start -> earliest separator of previous month
    frame._time_jump("month", -1)
    assert frame.msg_list.GetFirstSelected() == jan

    frame.Destroy()
    app.Destroy()


def test_time_jump_year_moves_between_years(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    by_year = {}
    for i in _separators(frame):
        by_year.setdefault(frame.rows[i].date.year, i)  # earliest separator of each year
    y2025, y2026 = by_year[2025], by_year[2026]

    frame._select_row(y2025)
    frame._time_jump("year", 1)  # 2025 -> 2026
    assert frame.msg_list.GetFirstSelected() == y2026

    # smart previous from 2026's start -> earliest separator of 2025
    frame._time_jump("year", -1)
    assert frame.msg_list.GetFirstSelected() == y2025

    frame.Destroy()
    app.Destroy()


def _key_event(keycode, shift=False, ctrl=False):
    evt = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    evt.SetKeyCode(keycode)
    evt.SetShiftDown(shift)
    evt.SetControlDown(ctrl)
    return evt


def _focus_message_list(frame):
    """Show the frame and focus the message list so on_char_hook's focus guard passes."""
    frame.Show()
    frame.msg_list.SetFocus()
    wx.Yield()
    assert wx.Window.FindFocus() is frame.msg_list


def test_on_char_hook_shift_arrow_jumps_day(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    _focus_message_list(frame)
    seps = _separators(frame)

    frame._select_row(seps[0])
    frame.on_char_hook(_key_event(wx.WXK_DOWN, shift=True))  # Shift+Down -> next day
    assert frame.msg_list.GetFirstSelected() == seps[1]

    frame.Destroy()
    app.Destroy()


def test_on_char_hook_ctrl_arrow_jumps_month(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    _focus_message_list(frame)
    by_month = {}
    for i in _separators(frame):
        key = (frame.rows[i].date.year, frame.rows[i].date.month)
        by_month.setdefault(key, i)
    jan, mar = by_month[(2025, 1)], by_month[(2025, 3)]

    frame._select_row(jan)
    frame.on_char_hook(_key_event(wx.WXK_DOWN, ctrl=True))  # Ctrl+Down -> next month
    assert frame.msg_list.GetFirstSelected() == mar

    frame.Destroy()
    app.Destroy()


def test_on_char_hook_page_keys_jump_year(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    _focus_message_list(frame)
    by_year = {}
    for i in _separators(frame):
        by_year.setdefault(frame.rows[i].date.year, i)
    y2025, y2026 = by_year[2025], by_year[2026]

    frame._select_row(y2025)
    frame.on_char_hook(_key_event(wx.WXK_PAGEDOWN))  # Page Down -> next year
    assert frame.msg_list.GetFirstSelected() == y2026

    frame.Destroy()
    app.Destroy()


def test_on_char_hook_ctrl_shift_arrow_does_not_jump(tmp_path):
    # Ctrl+Shift+Arrow is ambiguous (matches neither day nor month) and must be
    # left alone for the default list behavior, not hijacked as a time jump.
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    _focus_message_list(frame)
    seps = _separators(frame)

    frame._select_row(seps[0])
    frame.on_char_hook(_key_event(wx.WXK_DOWN, shift=True, ctrl=True))
    assert frame.msg_list.GetFirstSelected() == seps[0]  # unchanged

    frame.Destroy()
    app.Destroy()


def test_normal_rows_have_no_conv(tmp_path):
    app = wx.App()
    frame = _frame_with_multi(tmp_path)
    assert frame.rows
    for row in frame.rows:
        assert row.conv is None  # conv is only set on global-result rows
    frame.Destroy()
    app.Destroy()
