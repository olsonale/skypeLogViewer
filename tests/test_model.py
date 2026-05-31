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


def test_export_data_holds_conversations():
    data = ExportData(user_id="8:me", conversations=[])
    assert data.user_id == "8:me"
    assert data.conversations == []
