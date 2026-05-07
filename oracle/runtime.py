"""Shared agent factory used by the CLI, Streamlit UI, and eval harness.

Each entry point used to construct the same `Agent` plus tool-runner closure
inline. That closure dispatches the four tool names to their library functions.
Centralising it here keeps the wiring in one place so the entry points stay
focused on their own concerns (argument parsing, UI state, fixtures).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from oracle.agent import Agent
from oracle.graph.store import load_graph
from oracle.index.embeddings import embed_texts
from oracle.index.store import VectorStore
from oracle.tools.lineage import get_lineage
from oracle.tools.references import find_references
from oracle.tools.schema import get_schema
from oracle.tools.search import search_artifacts

EMBED_DIM = 1024
EMBED_MODEL = "voyage-3"


def build_agent(
    *,
    index_dir: Path,
    warehouse_path: Path,
    search_dir: Path,
) -> tuple[Agent, VectorStore]:
    """Wire a ready-to-use Agent against persisted graph + vector index.

    Returns the agent and the underlying vector store so the caller can close
    it when done.
    """
    import anthropic
    import voyageai

    graph = load_graph(index_dir / "graph.json")
    vstore = VectorStore(path=index_dir / "vectors.duckdb", dim=EMBED_DIM)
    voyage = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    def embed(texts: list[str], input_type: str = "document") -> list[list[float]]:
        return embed_texts(texts, client=voyage, model=EMBED_MODEL, input_type=input_type)

    def runner(name: str, args: dict) -> Any:
        if name == "search_artifacts":
            return search_artifacts(args["query"], k=args.get("k", 5), store=vstore, embed_fn=embed)
        if name == "get_lineage":
            return get_lineage(
                graph,
                node_id=args["node_id"],
                direction=args["direction"],
                depth=args.get("depth", 3),
            )
        if name == "get_schema":
            return get_schema(args["table"], warehouse_path=warehouse_path)
        if name == "find_references":
            return find_references(args["needle"], search_dirs=[search_dir])
        return {"error": f"unknown tool: {name}"}

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return Agent(client=client, tool_runner=runner), vstore
