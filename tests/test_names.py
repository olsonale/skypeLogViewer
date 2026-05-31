from skype_log_viewer.names import NameResolver, pretty_id


def test_own_id_resolves_to_you():
    r = NameResolver("8:me")
    assert r.name_for("8:me") == "You"


def test_learned_name_is_used():
    r = NameResolver("8:me")
    r.learn("8:alice", "Alice")
    assert r.name_for("8:alice") == "Alice"


def test_first_learned_name_wins():
    r = NameResolver("8:me")
    r.learn("8:alice", "Alice")
    r.learn("8:alice", "Alice (work)")
    assert r.name_for("8:alice") == "Alice"


def test_unknown_id_falls_back_to_pretty_id():
    r = NameResolver("8:me")
    assert r.name_for("8:live:.cid.123") == "live:.cid.123"


def test_blank_name_is_ignored():
    r = NameResolver("8:me")
    r.learn("8:alice", None)
    r.learn("8:alice", "")
    assert r.name_for("8:alice") == "alice"


def test_pretty_id_strips_prefixes():
    assert pretty_id("8:live:.cid.123") == "live:.cid.123"
    assert pretty_id("8:bob") == "bob"
    assert pretty_id("19:thread@thread.skype") == "19:thread@thread.skype"
