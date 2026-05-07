"""get_schema tool: read columns + row count from the warehouse."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


def get_schema(table: str, *, warehouse_path: Path) -> dict[str, Any]:
    if "." not in table:
        return {"error": f"table must be qualified (schema.name): {table}"}
    schema, name = table.split(".", 1)

    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position
            """,
            [schema, name],
        ).fetchall()
        if not rows:
            return {"error": f"table not found: {table}"}
        columns = [{"name": r[0], "dtype": r[1], "nullable": r[2] == "YES"} for r in rows]
        row_count = con.execute(f'SELECT COUNT(*) FROM "{schema}"."{name}"').fetchone()[0]
        return {"table": table, "columns": columns, "row_count": row_count}
    finally:
        con.close()
