import networkx as nx

from oracle.tools.lineage import get_lineage


def _sample_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_node("model:stg_users", kind="model", name="stg_users", file_path="models/stg_users.sql")
    g.add_node("model:fct_users", kind="model", name="fct_users", file_path="models/fct_users.sql")
    g.add_node("model:dim_geo", kind="model", name="dim_geo", file_path="models/dim_geo.sql")
    g.add_edge("model:stg_users", "model:fct_users", relation="depends_on")
    g.add_edge("model:stg_users", "model:dim_geo", relation="depends_on")
    return g


def test_get_lineage_upstream():
    g = _sample_graph()
    hits = get_lineage(g, node_id="model:fct_users", direction="up", depth=1)
    ids = {h["node_id"] for h in hits}
    assert ids == {"model:stg_users"}


def test_get_lineage_downstream():
    g = _sample_graph()
    hits = get_lineage(g, node_id="model:stg_users", direction="down", depth=1)
    ids = {h["node_id"] for h in hits}
    assert ids == {"model:fct_users", "model:dim_geo"}


def test_get_lineage_includes_relation_and_file():
    g = _sample_graph()
    hits = get_lineage(g, node_id="model:fct_users", direction="up", depth=1)
    assert hits[0]["relation"] == "depends_on"
    assert hits[0]["file_path"] == "models/stg_users.sql"
