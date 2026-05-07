"""DuckDB-backed vector store using the VSS extension.

We use the same engine that hosts the warehouse — one less dependency
and a clean storyline ("the warehouse and the index are the same engine").
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


class VectorStore:
    def __init__(self, path: Path, dim: int) -> None:
        self.path = Path(path)
        self.dim = dim
        self._con = duckdb.connect(str(self.path))
        self._con.execute("INSTALL vss; LOAD vss;")
        self._con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS embeddings (
                id VARCHAR PRIMARY KEY,
                text VARCHAR,
                vector FLOAT[{dim}]
            )
            """
        )

    def upsert(self, records: list[dict[str, Any]]) -> None:
        self._con.executemany(
            """
            INSERT OR REPLACE INTO embeddings (id, text, vector)
            VALUES (?, ?, ?)
            """,
            [(r["id"], r["text"], r["vector"]) for r in records],
        )

    def search(self, vector: list[float], k: int = 5) -> list[dict[str, Any]]:
        rows = self._con.execute(
            """
            SELECT id, text, array_distance(vector, ?::FLOAT[{dim}]) AS dist
            FROM embeddings
            ORDER BY dist ASC
            LIMIT ?
            """.format(dim=self.dim),
            [vector, k],
        ).fetchall()
        return [{"id": r[0], "text": r[1], "distance": r[2]} for r in rows]

    def count(self) -> int:
        return self._con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    def close(self) -> None:
        self._con.close()
