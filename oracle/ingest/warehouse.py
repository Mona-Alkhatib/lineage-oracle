"""Read warehouse metadata from DuckDB's information_schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb

SYSTEM_SCHEMAS = {"information_schema", "main", "pg_catalog"}


@dataclass
class WarehouseColumn:
    name: str
    dtype: str
    nullable: bool = True


@dataclass
class WarehouseTable:
    schema: str
    name: str
    row_count: int = 0
    columns: list[WarehouseColumn] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass
class Warehouse:
    tables: list[WarehouseTable]


def read_warehouse(path: Path) -> Warehouse:
    con = duckdb.connect(str(path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT table_schema, table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            ORDER BY table_schema, table_name, ordinal_position
            """
        ).fetchall()

        tables: dict[tuple[str, str], WarehouseTable] = {}
        for schema, name, col, dtype, nullable in rows:
            if schema in SYSTEM_SCHEMAS:
                continue
            key = (schema, name)
            tables.setdefault(key, WarehouseTable(schema=schema, name=name))
            tables[key].columns.append(
                WarehouseColumn(name=col, dtype=dtype, nullable=nullable == "YES")
            )

        for table in tables.values():
            count = con.execute(
                f'SELECT COUNT(*) FROM "{table.schema}"."{table.name}"'
            ).fetchone()[0]
            table.row_count = count

        return Warehouse(tables=list(tables.values()))
    finally:
        con.close()
