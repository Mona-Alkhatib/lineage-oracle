import networkx as nx

from oracle.graph.store import load_graph, save_graph


def test_save_and_load_round_trip(tmp_path):
    g = nx.DiGraph()
    g.add_node("model:foo", kind="model", name="foo", file_path="models/foo.sql")
    g.add_node("model:bar", kind="model", name="bar", file_path="models/bar.sql")
    g.add_edge("model:foo", "model:bar", relation="depends_on")

    path = tmp_path / "graph.json"
    save_graph(g, path)
    loaded = load_graph(path)

    assert set(loaded.nodes) == {"model:foo", "model:bar"}
    assert loaded.has_edge("model:foo", "model:bar")
    assert loaded.edges["model:foo", "model:bar"]["relation"] == "depends_on"
    assert loaded.nodes["model:foo"]["file_path"] == "models/foo.sql"
