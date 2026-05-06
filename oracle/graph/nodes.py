"""Node ID conventions used throughout the lineage graph.

Every node in the graph has a stable string ID of the form `<kind>:<name>`.
This makes it cheap to serialize (just strings) and easy for the agent to
reason about (`model:stg_users` is self-describing).
"""
from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    SOURCE = "source"
    MODEL = "model"
    COLUMN = "column"
    DAG = "dag"
    TASK = "task"


def make_id(kind: NodeKind, name: str) -> str:
    return f"{kind.value}:{name}"


def parse_id(node_id: str) -> tuple[NodeKind, str]:
    if ":" not in node_id:
        raise ValueError(f"invalid node id: {node_id}")
    prefix, name = node_id.split(":", 1)
    try:
        kind = NodeKind(prefix)
    except ValueError as exc:
        raise ValueError(f"unknown node kind: {prefix}") from exc
    return kind, name
