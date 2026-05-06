"""Parse dbt manifest.json into typed nodes.

The manifest is the canonical artifact dbt produces from a parse. We never
shell out to dbt at query time — we read the JSON directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Column:
    name: str
    description: str = ""


@dataclass
class DbtNode:
    name: str
    resource_type: str  # "model" | "source" | "seed"
    file_path: str
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    columns: list[Column] = field(default_factory=list)


@dataclass
class DbtManifest:
    nodes: list[DbtNode]


def _short_name(qualified: str) -> str:
    """Map 'model.jaffle.stg_users' -> 'stg_users'."""
    return qualified.split(".")[-1]


def _build_node(qualified_id: str, raw: dict) -> DbtNode:
    return DbtNode(
        name=raw["name"],
        resource_type=raw["resource_type"],
        file_path=raw.get("original_file_path", ""),
        description=raw.get("description", ""),
        depends_on=[_short_name(d) for d in raw.get("depends_on", {}).get("nodes", [])],
        columns=[
            Column(name=c["name"], description=c.get("description", ""))
            for c in raw.get("columns", {}).values()
        ],
    )


def parse_manifest(path: Path) -> DbtManifest:
    data = json.loads(Path(path).read_text())
    nodes = [_build_node(qid, n) for qid, n in data.get("nodes", {}).items()]
    nodes.extend(_build_node(qid, s) for qid, s in data.get("sources", {}).items())
    return DbtManifest(nodes=nodes)
