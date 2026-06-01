from datetime import datetime, timezone
from skype_log_viewer.model import Message, Conversation, ExportData


def _msg(text="hi", system=False):
    return Message(
        id="1",
        sender_id="8:alice",
        sender_name="Alice",
        timestamp=datetime(2025, 3, 19, 21, 18, tzinfo=timezone.utc),
        msgtype="RichText",
        clean_text=text,
        is_system=system,
    )


def test_conversation_message_count():
    conv = Conversation(
        id="8:alice",
        display_name="Alice",
        is_group=False,
        member_count=2,
        messages=[_msg(), _msg()],
    )
    assert conv.message_count == 2


def test_has_messages_true_with_a_real_message():
    conv = Conversation(
        id="8:alice",
        display_name="Alice",
        is_group=False,
        member_count=2,
        messages=[_msg(system=True), _msg(system=False)],
    )
    assert conv.has_messages is True


def test_has_messages_false_when_only_system_events():
    conv = Conversation(
        id="19:grouproom@thread.skype",
        display_name="Lonely Group",
        is_group=True,
        member_count=1,
        messages=[_msg(system=True), _msg(system=True)],
    )
    assert conv.has_messages is False


def test_has_messages_false_when_no_messages():
    conv = Conversation(
        id="8:empty",
        display_name="Empty",
        is_group=False,
        member_count=2,
        messages=[],
    )
    assert conv.has_messages is False


def test_export_data_holds_conversations():
    data = ExportData(user_id="8:me", conversations=[])
    assert data.user_id == "8:me"
    assert data.conversations == []
