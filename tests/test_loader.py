from datetime import timezone
from pathlib import Path

from skype_log_viewer.loader import load_export

FIXTURE = Path(__file__).parent / "fixtures" / "sample_export.json"


def test_load_basic_shape():
    data = load_export(FIXTURE)
    assert data.user_id == "8:me"
    assert len(data.conversations) == 3


def test_conversations_sorted_alphabetically():
    data = load_export(FIXTURE)
    names = [c.display_name for c in data.conversations]
    assert names == sorted(names, key=str.casefold)


def test_messages_sorted_chronologically():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    assert [m.clean_text for m in alice.messages] == ["first message", "second message"]


def test_own_message_labeled_you():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    first = alice.messages[0]
    assert first.sender_id == "8:me"
    assert first.sender_name == "You"


def test_other_message_uses_display_name():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    assert alice.messages[1].sender_name == "Alice"


def test_timestamps_are_utc_aware():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    ts = alice.messages[0].timestamp
    assert ts.tzinfo is not None
    assert ts.utcoffset() == timezone.utc.utcoffset(None)


def test_group_detection_and_member_count():
    data = load_export(FIXTURE)
    group = next(c for c in data.conversations if c.id == "19:grouproom@thread.skype")
    assert group.is_group is True
    assert group.member_count == 8


def test_one_to_one_member_count_defaults_to_two():
    data = load_export(FIXTURE)
    alice = next(c for c in data.conversations if c.id == "8:alice")
    assert alice.is_group is False
    assert alice.member_count == 2


def test_system_event_cleaned_and_flagged():
    data = load_export(FIXTURE)
    group = next(c for c in data.conversations if c.id == "19:grouproom@thread.skype")
    event = group.messages[0]
    assert event.is_system is True
    assert event.clean_text == "[Alice added Bob]"


def test_cache_round_trip(tmp_path):
    from skype_log_viewer.loader import load_with_cache

    cache_dir = tmp_path / "cache"
    first = load_with_cache(FIXTURE, cache_dir)
    # a cache file should now exist
    assert any(cache_dir.glob("*.pickle"))
    second = load_with_cache(FIXTURE, cache_dir)
    assert second.user_id == first.user_id
    assert len(second.conversations) == len(first.conversations)


def test_corrupt_cache_falls_back_to_parse(tmp_path):
    from skype_log_viewer.loader import load_with_cache, _cache_path

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    bad = _cache_path(FIXTURE, cache_dir)
    bad.write_bytes(b"not a pickle")
    data = load_with_cache(FIXTURE, cache_dir)
    assert data.user_id == "8:me"
