from oracle.graph.nodes import NodeKind, make_id, parse_id


def test_make_and_parse_round_trip():
    node_id = make_id(NodeKind.MODEL, "stg_users")
    kind, name = parse_id(node_id)
    assert kind == NodeKind.MODEL
    assert name == "stg_users"


def test_column_id_uses_qualified_name():
    node_id = make_id(NodeKind.COLUMN, "users.signup_country")
    assert node_id == "column:users.signup_country"


def test_unknown_kind_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_id("notakind:foo")
