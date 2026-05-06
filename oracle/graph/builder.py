"""Construct the lineage graph from parsed dbt + Airflow + warehouse inputs."""
from __future__ import annotations

import networkx as nx

from oracle.graph.nodes import NodeKind, make_id
from oracle.ingest.airflow import AirflowDag
from oracle.ingest.dbt import DbtManifest
from oracle.ingest.warehouse import Warehouse


def _add_dbt(graph: nx.DiGraph, manifest: DbtManifest) -> None:
    for node in manifest.nodes:
        kind = NodeKind.SOURCE if node.resource_type == "source" else NodeKind.MODEL
        node_id = make_id(kind, node.name)
        graph.add_node(
            node_id,
            kind=kind.value,
            name=node.name,
            file_path=node.file_path,
            description=node.description,
        )
        for col in node.columns:
            col_id = make_id(NodeKind.COLUMN, f"{node.name}.{col.name}")
            graph.add_node(col_id, kind=NodeKind.COLUMN.value, name=col.name)
            graph.add_edge(node_id, col_id, relation="has_column")
        for upstream in node.depends_on:
            up_id_model = make_id(NodeKind.MODEL, upstream)
            up_id_source = make_id(NodeKind.SOURCE, upstream)
            up_id = up_id_model if up_id_model in graph.nodes else up_id_source
            graph.add_edge(up_id, node_id, relation="depends_on")


def _add_dags(graph: nx.DiGraph, dags: list[AirflowDag]) -> None:
    for dag in dags:
        dag_id = make_id(NodeKind.DAG, dag.dag_id)
        graph.add_node(
            dag_id,
            kind=NodeKind.DAG.value,
            name=dag.dag_id,
            file_path=str(dag.file_path),
            schedule=dag.schedule,
        )
        for table in dag.writes:
            # `writes` strings look like "raw.users" — the source node is keyed by
            # the table's short name (e.g. `source:users`), matching dbt's source name.
            short = table.split(".")[-1]
            target = make_id(NodeKind.SOURCE, short)
            if target in graph.nodes:
                graph.add_edge(dag_id, target, relation="refreshes")


def _add_warehouse(graph: nx.DiGraph, warehouse: Warehouse) -> None:
    for table in warehouse.tables:
        # Annotate any matching source node with row_count + dtype info.
        source_id = make_id(NodeKind.SOURCE, table.name)
        if source_id in graph.nodes:
            graph.nodes[source_id]["row_count"] = table.row_count
            graph.nodes[source_id]["dtypes"] = {c.name: c.dtype for c in table.columns}


def build_graph(
    manifest: DbtManifest,
    dags: list[AirflowDag],
    warehouse: Warehouse | None,
) -> nx.DiGraph:
    g: nx.DiGraph = nx.DiGraph()
    _add_dbt(g, manifest)
    _add_dags(g, dags)
    if warehouse is not None:
        _add_warehouse(g, warehouse)
    return g
