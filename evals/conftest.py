"""Shared fixtures for the eval harness."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
INDEX_DIR = Path(".oracle")
WAREHOUSE = Path("data/jaffle_shop/dbt_project/jaffle_shop.duckdb")
SEARCH_DIR = Path("data/jaffle_shop")


def load_eval_set() -> list[dict]:
    return json.loads(EVAL_SET_PATH.read_text())


@pytest.fixture(scope="session")
def agent():
    import anthropic
    import voyageai

    from oracle.agent import Agent
    from oracle.graph.store import load_graph
    from oracle.index.embeddings import embed_texts
    from oracle.index.store import VectorStore
    from oracle.tools.lineage import get_lineage
    from oracle.tools.references import find_references
    from oracle.tools.schema import get_schema
    from oracle.tools.search import search_artifacts

    graph = load_graph(INDEX_DIR / "graph.json")
    vstore = VectorStore(path=INDEX_DIR / "vectors.duckdb", dim=1024)
    voyage = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    def embed(texts, input_type="document"):
        return embed_texts(texts, client=voyage, model="voyage-3", input_type=input_type)

    def runner(name, args):
        if name == "search_artifacts":
            return search_artifacts(args["query"], k=args.get("k", 5), store=vstore, embed_fn=embed)
        if name == "get_lineage":
            return get_lineage(graph, node_id=args["node_id"], direction=args["direction"], depth=args.get("depth", 3))
        if name == "get_schema":
            return get_schema(args["table"], warehouse_path=WAREHOUSE)
        if name == "find_references":
            return find_references(args["needle"], search_dirs=[SEARCH_DIR])
        return {"error": f"unknown tool: {name}"}

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return Agent(client=client, tool_runner=runner)
