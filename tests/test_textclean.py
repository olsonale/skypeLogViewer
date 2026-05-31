from skype_log_viewer.textclean import clean_content, is_system_event


def names(skype_id):
    return {"8:alice": "Alice", "8:bob": "Bob"}.get(skype_id, skype_id)


def test_plain_richtext():
    assert clean_content("Every day I look forward.", "RichText") == "Every day I look forward."


def test_decodes_entities():
    assert clean_content("a &amp; b &lt;c&gt;", "RichText") == "a & b <c>"


def test_emoticon_keeps_inner_text():
    assert clean_content('haha <ss type="laugh">:D</ss>', "RichText") == "haha :D"


def test_mention_keeps_name():
    assert clean_content('<at id="8:bob">Bob</at> hello', "RichText") == "Bob hello"


def test_link_text_equal_to_href_shows_once():
    out = clean_content('see <a href="https://x.com">https://x.com</a>', "RichText")
    assert out == "see https://x.com"


def test_link_with_distinct_text_shows_both():
    out = clean_content('see <a href="https://x.com">my site</a>', "RichText")
    assert out == "see my site (https://x.com)"


def test_quote_formats_with_author_and_reply():
    raw = (
        '<quote author="8:bob" authorname="Bob" timestamp="1">'
        "<legacyquote>[1] Bob: </legacyquote>need to mirror you"
        "<legacyquote>&lt;&lt;&lt; </legacyquote></quote>"
        "I thought you said marry you"
    )
    out = clean_content(raw, "RichText")
    assert out == 'Quote from Bob: "need to mirror you". I thought you said marry you'


def test_photo_label():
    assert clean_content('<URIObject type="Picture.1">x</URIObject>', "RichText/UriObject") == "[Photo]"


def test_voice_label():
    assert clean_content('<URIObject type="Audio.1">x</URIObject>', "RichText/Media_AudioMsg") == "[Voice message]"


def test_video_label():
    assert clean_content('<URIObject type="Video.1">x</URIObject>', "RichText/Media_Video") == "[Video]"


def test_file_label_uses_original_name():
    raw = '<URIObject type="File.1">x<OriginalName v="report.docx"></OriginalName></URIObject>'
    assert clean_content(raw, "RichText/Media_GenericFile") == "[File: report.docx]"


def test_poll_label_uses_title():
    raw = '<URIObject type="Poll" title="Switch to Skype?">Switch?</URIObject>'
    assert clean_content(raw, "Poll") == "[Poll: Switch to Skype?]"


def test_call_with_duration():
    raw = '<partlist type="ended"><part><duration>4</duration></part></partlist>'
    assert clean_content(raw, "Event/Call") == "[Call, 4 seconds]"


def test_call_ended_no_duration():
    raw = '<partlist type="ended"></partlist>'
    assert clean_content(raw, "Event/Call") == "[Call ended]"


def test_add_member_join_when_initiator_equals_target():
    raw = "<addmember><initiator>8:alice</initiator><target>8:alice</target></addmember>"
    assert clean_content(raw, "ThreadActivity/AddMember", name_lookup=names) == "[Alice joined the chat]"


def test_add_member_added_by_other():
    raw = "<addmember><initiator>8:alice</initiator><target>8:bob</target></addmember>"
    assert clean_content(raw, "ThreadActivity/AddMember", name_lookup=names) == "[Alice added Bob]"


def test_delete_member_left():
    raw = "<deletemember><initiator>8:bob</initiator><target>8:bob</target></deletemember>"
    assert clean_content(raw, "ThreadActivity/DeleteMember", name_lookup=names) == "[Bob left the chat]"


def test_topic_update():
    raw = "<topicupdate><value>SLM</value></topicupdate>"
    assert clean_content(raw, "ThreadActivity/TopicUpdate") == '[Topic changed to "SLM"]'


def test_is_system_event():
    assert is_system_event("ThreadActivity/AddMember") is True
    assert is_system_event("Notice") is True
    assert is_system_event("RichText") is False
    assert is_system_event("Event/Call") is False


def test_none_content_is_empty_string():
    assert clean_content(None, "RichText") == ""
