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

    edges_iter = graph.in_edges if direction == "up" else graph.out_edges
    other = (lambda u, v: u) if direction == "up" else (lambda u, v: v)

    visited: set[str] = set()
    frontier: list[tuple[str, int]] = [(node_id, 0)]
    results: list[dict[str, Any]] = []

    while frontier:
        current, hop = frontier.pop()
        if hop >= depth:
            continue
        for u, v, data in edges_iter(current, data=True):
            neighbor = other(u, v)
            if neighbor in visited:
                continue
            visited.add(neighbor)
            ndata = graph.nodes[neighbor]
            results.append(
                {
                    "node_id": neighbor,
                    "kind": ndata.get("kind", ""),
                    "name": ndata.get("name", ""),
                    "relation": data.get("relation", ""),
                    "file_path": ndata.get("file_path", ""),
                    "hop": hop + 1,
                }
            )
            frontier.append((neighbor, hop + 1))

    return results
