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
