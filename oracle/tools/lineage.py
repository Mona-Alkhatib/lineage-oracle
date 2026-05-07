"""get_lineage tool: graph traversal up or down from a node."""
from __future__ import annotations

from typing import Any, Literal

import networkx as nx

Direction = Literal["up", "down"]


def get_lineage(
    graph: nx.DiGraph,
    *,
    node_id: str,
    direction: Direction,
    depth: int = 3,
) -> list[dict[str, Any]]:
    if node_id not in graph.nodes:
        return []

    visited: set[str] = set()
    frontier: list[tuple[str, int]] = [(node_id, 0)]
    results: list[dict[str, Any]] = []

    while frontier:
        current, hop = frontier.pop()
        if hop >= depth:
            continue
        for neighbor, edge_data in _neighbors(graph, current, direction):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            ndata = graph.nodes[neighbor]
            results.append(
                {
                    "node_id": neighbor,
                    "kind": ndata.get("kind", ""),
                    "name": ndata.get("name", ""),
                    "relation": edge_data.get("relation", ""),
                    "file_path": ndata.get("file_path", ""),
                    "hop": hop + 1,
                }
            )
            frontier.append((neighbor, hop + 1))

    return results


def _neighbors(graph: nx.DiGraph, node: str, direction: Direction):
    """Yield (neighbor_id, edge_data) pairs in the requested direction."""
    if direction == "up":
        for predecessor, _, data in graph.in_edges(node, data=True):
            yield predecessor, data
    else:
        for _, successor, data in graph.out_edges(node, data=True):
            yield successor, data
