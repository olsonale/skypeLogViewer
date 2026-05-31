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
