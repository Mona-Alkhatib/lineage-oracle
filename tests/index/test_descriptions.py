import networkx as nx

from oracle.index.descriptions import describe_node


def test_describe_model_includes_name_and_inputs():
    g = nx.DiGraph()
    g.add_node("model:fct_users", kind="model", name="fct_users", description="user fact")
    g.add_node("model:stg_users", kind="model", name="stg_users", description="staging users")
    g.add_edge("model:stg_users", "model:fct_users", relation="depends_on")

    desc = describe_node(g, "model:fct_users")
    assert "fct_users" in desc
    assert "stg_users" in desc
    assert "user fact" in desc.lower() or "user fact" in desc


def test_describe_source_lists_columns():
    g = nx.DiGraph()
    g.add_node("source:users", kind="source", name="users", description="raw users table")
    g.add_node("column:users.user_id", kind="column", name="user_id")
    g.add_node("column:users.signup_country", kind="column", name="signup_country")
    g.add_edge("source:users", "column:users.user_id", relation="has_column")
    g.add_edge("source:users", "column:users.signup_country", relation="has_column")

    desc = describe_node(g, "source:users")
    assert "user_id" in desc
    assert "signup_country" in desc
