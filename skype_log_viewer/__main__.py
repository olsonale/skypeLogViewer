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
