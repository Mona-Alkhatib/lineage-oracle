import duckdb
import pytest

from oracle.ingest.warehouse import read_warehouse


@pytest.fixture
def warehouse(tmp_path):
    db = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE SCHEMA raw")
    con.execute("CREATE TABLE raw.users (user_id INTEGER, signup_country VARCHAR)")
    con.execute("INSERT INTO raw.users VALUES (1, 'US'), (2, 'JP')")
    con.close()
    return db


def test_read_warehouse_lists_tables(warehouse):
    result = read_warehouse(warehouse)
    names = {t.qualified_name for t in result.tables}
    assert "raw.users" in names


def test_read_warehouse_lists_columns(warehouse):
    result = read_warehouse(warehouse)
    users = next(t for t in result.tables if t.qualified_name == "raw.users")
    cols = {c.name: c.dtype for c in users.columns}
    assert cols == {"user_id": "INTEGER", "signup_country": "VARCHAR"}


def test_read_warehouse_records_row_count(warehouse):
    result = read_warehouse(warehouse)
    users = next(t for t in result.tables if t.qualified_name == "raw.users")
    assert users.row_count == 2
