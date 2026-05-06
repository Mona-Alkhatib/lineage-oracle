"""Serialize/deserialize the lineage graph as JSON.

JSON is chosen over pickle so the artifact is human-readable and
version-controllable.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph


def save_graph(graph: nx.DiGraph, path: Path) -> None:
    data = json_graph.node_link_data(graph, edges="edges")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, default=str))


def load_graph(path: Path) -> nx.DiGraph:
    data = json.loads(Path(path).read_text())
    graph = json_graph.node_link_graph(data, directed=True, edges="edges")
    return graph
