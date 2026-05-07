"""Generate a short natural-language description for each graph node.

These descriptions are what we embed for semantic search. We assemble them
deterministically from graph structure (no LLM call needed for v1) so
indexing is fast and reproducible. A future version can use Claude to
write richer descriptions.
"""
from __future__ import annotations

import networkx as nx


def _columns_of(graph: nx.DiGraph, node_id: str) -> list[str]:
    return [
        graph.nodes[succ]["name"]
        for _, succ, data in graph.out_edges(node_id, data=True)
        if data.get("relation") == "has_column"
    ]


def _upstream_of(graph: nx.DiGraph, node_id: str) -> list[str]:
    return [
        graph.nodes[pred]["name"]
        for pred, _, data in graph.in_edges(node_id, data=True)
        if data.get("relation") == "depends_on"
    ]


def describe_node(graph: nx.DiGraph, node_id: str) -> str:
    data = graph.nodes[node_id]
    kind = data.get("kind", "")
    name = data.get("name", node_id)
    desc = data.get("description", "")
    parts: list[str] = [f"{kind} {name}."]
    if desc:
        parts.append(desc)
    cols = _columns_of(graph, node_id)
    if cols:
        parts.append(f"Columns: {', '.join(cols)}.")
    ups = _upstream_of(graph, node_id)
    if ups:
        parts.append(f"Built from: {', '.join(ups)}.")
    return " ".join(parts)
