"""Typer CLI entry point.

Two commands:
- `oracle index <project_dir>` — parse + build graph + embed + persist.
- `oracle ask "<question>"` — load index and run the agent loop.

The CLI is intentionally thin; all logic lives in the library.
"""
from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv

app = typer.Typer(no_args_is_help=True)


@app.command()
def index(
    manifest: Path = typer.Option(..., help="Path to dbt manifest.json"),
    dags_dir: Path = typer.Option(..., help="Directory containing Airflow DAG .py files"),
    warehouse: Path = typer.Option(..., help="Path to DuckDB warehouse file"),
    out_dir: Path = typer.Option(Path(".oracle"), help="Output directory"),
) -> None:
    """Parse inputs, build the graph + index, and persist artifacts."""
    load_dotenv()
    from oracle.ingest.airflow import parse_dag_file
    from oracle.ingest.dbt import parse_manifest
    from oracle.ingest.warehouse import read_warehouse
    from oracle.graph.builder import build_graph
    from oracle.graph.store import save_graph
    from oracle.index.descriptions import describe_node
    from oracle.index.embeddings import embed_texts
    from oracle.index.store import VectorStore

    typer.echo("Parsing dbt manifest...")
    m = parse_manifest(manifest)

    typer.echo("Parsing Airflow DAGs...")
    dags = [parse_dag_file(p) for p in Path(dags_dir).glob("*.py")]

    typer.echo("Reading warehouse...")
    wh = read_warehouse(warehouse)

    typer.echo("Building graph...")
    g = build_graph(manifest=m, dags=dags, warehouse=wh)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_graph(g, out_dir / "graph.json")
    typer.echo(f"Saved {out_dir / 'graph.json'} ({g.number_of_nodes()} nodes)")

    typer.echo("Embedding nodes...")
    import voyageai
    voyage = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    node_ids = list(g.nodes)
    descriptions = [describe_node(g, n) for n in node_ids]
    vectors = embed_texts(descriptions, client=voyage, model="voyage-3", input_type="document")

    store = VectorStore(path=out_dir / "vectors.duckdb", dim=len(vectors[0]))
    store.upsert(
        [
            {"id": n, "text": d, "vector": v}
            for n, d, v in zip(node_ids, descriptions, vectors, strict=True)
        ]
    )
    store.close()
    typer.echo(f"Saved {out_dir / 'vectors.duckdb'} ({len(node_ids)} embeddings)")


@app.command()
def ask(
    question: str,
    out_dir: Path = typer.Option(Path(".oracle"), help="Index directory"),
    warehouse: Path = typer.Option(..., help="Path to DuckDB warehouse file"),
    search_dir: Path = typer.Option(..., help="Root for find_references"),
) -> None:
    """Ask Oracle a question."""
    load_dotenv()
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

    graph = load_graph(out_dir / "graph.json")
    vstore = VectorStore(path=out_dir / "vectors.duckdb", dim=1024)
    voyage = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    def embed(texts, input_type="document"):
        return embed_texts(texts, client=voyage, model="voyage-3", input_type=input_type)

    def runner(name: str, args: dict):
        if name == "search_artifacts":
            return search_artifacts(args["query"], k=args.get("k", 5), store=vstore, embed_fn=embed)
        if name == "get_lineage":
            return get_lineage(graph, node_id=args["node_id"], direction=args["direction"], depth=args.get("depth", 3))
        if name == "get_schema":
            return get_schema(args["table"], warehouse_path=warehouse)
        if name == "find_references":
            return find_references(args["needle"], search_dirs=[search_dir])
        return {"error": f"unknown tool: {name}"}

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    agent = Agent(client=client, tool_runner=runner)
    answer = agent.ask(question)
    typer.echo(answer)
    vstore.close()
