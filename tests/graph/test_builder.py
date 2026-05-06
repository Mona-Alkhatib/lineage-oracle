from pathlib import Path

from oracle.graph.builder import build_graph
from oracle.ingest.airflow import parse_dag_file
from oracle.ingest.dbt import parse_manifest

FIX = Path(__file__).parent.parent / "ingest" / "fixtures"


def test_build_graph_includes_all_dbt_nodes():
    manifest = parse_manifest(FIX / "manifest_minimal.json")
    g = build_graph(manifest=manifest, dags=[], warehouse=None)
    assert "model:stg_users" in g.nodes
    assert "model:fct_user_metrics" in g.nodes
    assert "source:users" in g.nodes


def test_build_graph_adds_depends_on_edges():
    manifest = parse_manifest(FIX / "manifest_minimal.json")
    g = build_graph(manifest=manifest, dags=[], warehouse=None)
    assert g.has_edge("model:stg_users", "model:fct_user_metrics")


def test_build_graph_adds_dag_writes_edges():
    manifest = parse_manifest(FIX / "manifest_minimal.json")
    dag = parse_dag_file(FIX / "sample_dag.py")
    g = build_graph(manifest=manifest, dags=[dag], warehouse=None)
    # The DAG declares it writes to raw.users; we link the dag node to the source node.
    assert g.has_edge("dag:users_ingest", "source:users")
