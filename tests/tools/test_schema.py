import duckdb
import pytest

from oracle.tools.schema import get_schema


@pytest.fixture
def warehouse(tmp_path):
    db = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE SCHEMA raw")
    con.execute("CREATE TABLE raw.users (user_id INTEGER, name VARCHAR)")
    con.execute("INSERT INTO raw.users VALUES (1, 'a'), (2, 'b'), (3, 'c')")
    con.close()
    return db


def test_get_schema_returns_columns(warehouse):
    result = get_schema("raw.users", warehouse_path=warehouse)
    cols = {c["name"]: c["dtype"] for c in result["columns"]}
    assert cols == {"user_id": "INTEGER", "name": "VARCHAR"}
    assert result["row_count"] == 3


def test_get_schema_unknown_table(warehouse):
    result = get_schema("raw.nope", warehouse_path=warehouse)
    assert result == {"error": "table not found: raw.nope"}
