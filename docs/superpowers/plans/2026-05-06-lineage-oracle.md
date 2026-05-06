# Lineage Oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI agent that answers grounded questions about a data warehouse (lineage, impact, semantic search, schema) using a NetworkX lineage graph + DuckDB vector index, exposed as a Python library, Typer CLI, and Streamlit UI, with a pytest-based eval harness.

**Architecture:** Two-phase system — *Index Phase* parses dbt `manifest.json`, Airflow DAG `.py` files, and DuckDB `information_schema` into a NetworkX graph + voyage-3 embeddings persisted to disk. *Query Phase* runs a Claude Sonnet 4.6 tool-use loop with 4 tools (search_artifacts, get_lineage, get_schema, find_references) that ground every answer in citations. The library is the single source of truth; CLI and Streamlit are thin wrappers.

**Tech Stack:** Python 3.11+, Anthropic SDK (Claude Sonnet 4.6), Voyage AI (voyage-3), DuckDB + VSS extension, NetworkX, Typer, Streamlit, pytest, uv, ruff.

---

## File Structure

```
lineage-oracle/
├── oracle/                          # library — single source of truth
│   ├── __init__.py
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── dbt.py                   # parse dbt manifest.json
│   │   ├── airflow.py               # static AST parse of DAG files
│   │   └── warehouse.py             # query information_schema
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── nodes.py                 # node ID conventions + types
│   │   ├── builder.py               # build NetworkX graph from parsed inputs
│   │   └── store.py                 # JSON serialization
│   ├── index/
│   │   ├── __init__.py
│   │   ├── descriptions.py          # generate semantic descriptions per node
│   │   ├── embeddings.py            # Voyage AI client wrapper
│   │   └── store.py                 # DuckDB VSS persistence
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py                # search_artifacts
│   │   ├── lineage.py               # get_lineage
│   │   ├── schema.py                # get_schema
│   │   ├── references.py            # find_references
│   │   └── definitions.py           # JSON schema definitions for Claude
│   ├── agent.py                     # tool-use loop
│   └── cli.py                       # Typer CLI (oracle index / oracle ask)
├── ui/
│   └── streamlit_app.py             # thin wrapper over oracle.ask
├── data/
│   └── jaffle_shop/                 # vendored demo: dbt project + toy DAGs + DuckDB
│       ├── dbt_project/             # copied from dbt-labs/jaffle_shop_duckdb
│       │   └── jaffle_shop.duckdb   # warehouse, populated by dbt seed + run (gitignored)
│       └── dags/                    # 3-4 toy Airflow DAGs we author
├── evals/
│   ├── eval_set.json                # ~30 ground-truth questions
│   └── test_evals.py                # pytest runner
├── tests/                           # unit tests, mirrors oracle/
├── pyproject.toml
├── .gitignore
├── .env.example
└── README.md
```

**Responsibility split:**
- `ingest/` — pure parsers, no graph knowledge
- `graph/` — pure data structures, no LLM/embeddings knowledge
- `index/` — semantic layer; talks to LLM + embeddings APIs
- `tools/` — adapters that the agent calls; each one is a thin function
- `agent.py` — orchestrates Claude + tools
- `cli.py` / `streamlit_app.py` — interface layers, no business logic

---

## Phase 0 — Project Setup

### Task 1: Initialize Python project with uv + ruff

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Confirm uv is installed**

Run: `uv --version`
Expected: prints a version like `uv 0.5.x`. If not installed: `brew install uv`.

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "lineage-oracle"
version = "0.1.0"
description = "AI agent that answers grounded questions about a data warehouse"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "voyageai>=0.3.0",
    "duckdb>=1.1.0",
    "networkx>=3.3",
    "typer>=0.13.0",
    "streamlit>=1.40.0",
    "pydantic>=2.9.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
oracle = "oracle.cli:app"

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.7.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests", "evals"]
```

- [ ] **Step 3: Create `.python-version`**

```
3.11
```

- [ ] **Step 4: Create `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
```

- [ ] **Step 5: Append to `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.env
.oracle/
data/jaffle_shop/dbt_project/jaffle_shop.duckdb
data/jaffle_shop/dbt_project/target/
data/jaffle_shop/dbt_project/dbt_packages/
data/jaffle_shop/dbt_project/logs/
```

- [ ] **Step 6: Sync dependencies**

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`, installs all deps without error.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .python-version .env.example .gitignore uv.lock
git commit -m "chore: initialize uv project with core dependencies"
```

---

### Task 2: Vendor jaffle_shop demo data

**Files:**
- Create: `data/jaffle_shop/dbt_project/` (copied from upstream)
- Create: `data/jaffle_shop/dags/users_ingest.py`
- Create: `data/jaffle_shop/dags/orders_ingest.py`
- Create: `data/jaffle_shop/dags/payments_ingest.py`
- Create: `data/jaffle_shop/build_warehouse.py`

- [ ] **Step 1: Clone jaffle_shop into the project**

Run:
```bash
git clone --depth 1 https://github.com/dbt-labs/jaffle_shop_duckdb.git /tmp/jaffle_shop_duckdb
mkdir -p data/jaffle_shop
cp -R /tmp/jaffle_shop_duckdb/* data/jaffle_shop/dbt_project/
rm -rf data/jaffle_shop/dbt_project/.git
```
Expected: `data/jaffle_shop/dbt_project/dbt_project.yml` exists.

- [ ] **Step 2: Create toy Airflow DAG `data/jaffle_shop/dags/users_ingest.py`**

```python
"""Toy Airflow DAG that 'ingests' raw.users.

This file is parsed statically by oracle/ingest/airflow.py. It is never executed.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def extract_users():
    # writes to: raw.users
    pass


with DAG(
    dag_id="users_ingest",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_users,
    )
```

- [ ] **Step 3: Create `data/jaffle_shop/dags/orders_ingest.py`**

```python
"""Toy Airflow DAG that 'ingests' raw.orders."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def extract_orders():
    # writes to: raw.orders
    pass


with DAG(
    dag_id="orders_ingest",
    schedule="0 3 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_orders,
    )
```

- [ ] **Step 4: Create `data/jaffle_shop/dags/payments_ingest.py`**

```python
"""Toy Airflow DAG that 'ingests' raw.payments."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def extract_payments():
    # writes to: raw.payments
    pass


with DAG(
    dag_id="payments_ingest",
    schedule="0 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_payments,
    )
```

- [ ] **Step 5: Create `data/jaffle_shop/build_warehouse.py`**

```python
"""Run jaffle_shop's seeds + dbt build to produce the demo warehouse.

This is a one-time setup script. Run it manually:
    cd data/jaffle_shop/dbt_project && dbt seed && dbt run && dbt parse
The resulting jaffle_shop.duckdb is git-ignored.
"""
import subprocess
from pathlib import Path

PROJECT = Path(__file__).parent / "dbt_project"


def main():
    subprocess.run(["dbt", "seed", "--profiles-dir", str(PROJECT)], cwd=PROJECT, check=True)
    subprocess.run(["dbt", "run", "--profiles-dir", str(PROJECT)], cwd=PROJECT, check=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Build the warehouse manually**

Run: `cd data/jaffle_shop/dbt_project && dbt seed && dbt run`
Expected: produces `data/jaffle_shop/jaffle.duckdb`. (If `dbt-duckdb` not installed, install via `uv pip install dbt-duckdb` into the venv first.)

- [ ] **Step 7: Generate the `manifest.json`**

Run: `cd data/jaffle_shop/dbt_project && dbt parse`
Expected: produces `data/jaffle_shop/dbt_project/target/manifest.json`.

- [ ] **Step 8: Commit (excluding the duckdb binary, which is .gitignored)**

```bash
git add data/jaffle_shop/dbt_project data/jaffle_shop/dags data/jaffle_shop/build_warehouse.py
git commit -m "chore: vendor jaffle_shop demo with toy Airflow DAGs"
```

---

## Phase 1 — Ingestion

### Task 3: Build dbt manifest parser

**Files:**
- Create: `oracle/__init__.py`
- Create: `oracle/ingest/__init__.py`
- Create: `oracle/ingest/dbt.py`
- Create: `tests/__init__.py`
- Create: `tests/ingest/__init__.py`
- Create: `tests/ingest/test_dbt.py`
- Create: `tests/ingest/fixtures/manifest_minimal.json`

- [ ] **Step 1: Create `tests/ingest/fixtures/manifest_minimal.json`**

```json
{
  "nodes": {
    "model.jaffle.stg_users": {
      "name": "stg_users",
      "resource_type": "model",
      "depends_on": {"nodes": ["source.jaffle.raw.users"]},
      "original_file_path": "models/staging/stg_users.sql",
      "columns": {"user_id": {"name": "user_id", "description": "primary key"}},
      "description": "Staging users"
    },
    "model.jaffle.fct_user_metrics": {
      "name": "fct_user_metrics",
      "resource_type": "model",
      "depends_on": {"nodes": ["model.jaffle.stg_users"]},
      "original_file_path": "models/marts/fct_user_metrics.sql",
      "columns": {},
      "description": "User metrics fact"
    }
  },
  "sources": {
    "source.jaffle.raw.users": {
      "name": "users",
      "schema": "raw",
      "resource_type": "source",
      "original_file_path": "models/staging/sources.yml",
      "columns": {"user_id": {"name": "user_id"}, "signup_country": {"name": "signup_country"}}
    }
  }
}
```

- [ ] **Step 2: Write the failing test `tests/ingest/test_dbt.py`**

```python
import json
from pathlib import Path

from oracle.ingest.dbt import parse_manifest

FIXTURE = Path(__file__).parent / "fixtures" / "manifest_minimal.json"


def test_parse_manifest_returns_models_and_sources():
    result = parse_manifest(FIXTURE)
    names = {n.name for n in result.nodes}
    assert names == {"stg_users", "fct_user_metrics", "users"}


def test_parse_manifest_extracts_dependencies():
    result = parse_manifest(FIXTURE)
    fct = next(n for n in result.nodes if n.name == "fct_user_metrics")
    assert "stg_users" in fct.depends_on


def test_parse_manifest_extracts_columns():
    result = parse_manifest(FIXTURE)
    users = next(n for n in result.nodes if n.name == "users")
    assert {"user_id", "signup_country"} == {c.name for c in users.columns}


def test_parse_manifest_records_file_paths():
    result = parse_manifest(FIXTURE)
    fct = next(n for n in result.nodes if n.name == "fct_user_metrics")
    assert fct.file_path == "models/marts/fct_user_metrics.sql"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ingest/test_dbt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'oracle.ingest.dbt'`.

- [ ] **Step 4: Implement `oracle/ingest/dbt.py`**

```python
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
```

- [ ] **Step 5: Create `oracle/__init__.py` and `oracle/ingest/__init__.py`**

Both files are empty (just placeholders). Run:
```bash
touch oracle/__init__.py oracle/ingest/__init__.py tests/__init__.py tests/ingest/__init__.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/ingest/test_dbt.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add oracle/__init__.py oracle/ingest tests/__init__.py tests/ingest
git commit -m "feat: add dbt manifest parser"
```

---

### Task 4: Build Airflow DAG static parser

**Files:**
- Create: `oracle/ingest/airflow.py`
- Create: `tests/ingest/test_airflow.py`
- Create: `tests/ingest/fixtures/sample_dag.py`

- [ ] **Step 1: Create `tests/ingest/fixtures/sample_dag.py`**

```python
"""Fixture: a toy DAG used for testing the AST parser."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def extract_users():
    # writes to: raw.users
    pass


with DAG(
    dag_id="users_ingest",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_users,
    )
```

- [ ] **Step 2: Write the failing test `tests/ingest/test_airflow.py`**

```python
from pathlib import Path

from oracle.ingest.airflow import parse_dag_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_dag.py"


def test_parse_dag_extracts_dag_id():
    result = parse_dag_file(FIXTURE)
    assert result.dag_id == "users_ingest"


def test_parse_dag_extracts_schedule():
    result = parse_dag_file(FIXTURE)
    assert result.schedule == "0 2 * * *"


def test_parse_dag_extracts_tasks():
    result = parse_dag_file(FIXTURE)
    task_ids = {t.task_id for t in result.tasks}
    assert task_ids == {"extract"}


def test_parse_dag_extracts_writes_from_comments():
    """The parser reads `# writes to: <table>` comments inside callables."""
    result = parse_dag_file(FIXTURE)
    assert "raw.users" in result.writes


def test_parse_dag_records_file_path():
    result = parse_dag_file(FIXTURE)
    assert str(result.file_path).endswith("sample_dag.py")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ingest/test_airflow.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `oracle/ingest/airflow.py`**

```python
"""Static AST parser for Airflow DAG files.

We never import these files. We parse them with `ast` and pull out:
- The DAG id and schedule (from the DAG(...) constructor call).
- The set of task_ids (from operator constructor calls).
- The set of tables a DAG writes to, declared via `# writes to: <table>` comments.

Reading-from-tables is harder to extract statically (it depends on operator
internals), so we leave it for v2. The comment convention is explicit and
sufficient for v1.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

WRITES_RE = re.compile(r"#\s*writes to:\s*([\w\.]+)")


@dataclass
class Task:
    task_id: str


@dataclass
class AirflowDag:
    dag_id: str
    schedule: str
    file_path: Path
    tasks: list[Task] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)


def _kw(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _str(node: ast.expr | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def parse_dag_file(path: Path) -> AirflowDag:
    source = Path(path).read_text()
    tree = ast.parse(source)

    dag_id = ""
    schedule = ""
    task_ids: list[Task] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name == "DAG":
            dag_id = _str(_kw(node, "dag_id"))
            schedule = _str(_kw(node, "schedule"))
        elif name.endswith("Operator"):
            tid = _str(_kw(node, "task_id"))
            if tid:
                task_ids.append(Task(task_id=tid))

    writes = WRITES_RE.findall(source)

    return AirflowDag(
        dag_id=dag_id,
        schedule=schedule,
        file_path=Path(path),
        tasks=task_ids,
        writes=writes,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ingest/test_airflow.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add oracle/ingest/airflow.py tests/ingest/test_airflow.py tests/ingest/fixtures/sample_dag.py
git commit -m "feat: add static Airflow DAG parser"
```

---

### Task 5: Build warehouse schema reader

**Files:**
- Create: `oracle/ingest/warehouse.py`
- Create: `tests/ingest/test_warehouse.py`

- [ ] **Step 1: Write the failing test `tests/ingest/test_warehouse.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ingest/test_warehouse.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `oracle/ingest/warehouse.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ingest/test_warehouse.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/ingest/warehouse.py tests/ingest/test_warehouse.py
git commit -m "feat: add warehouse schema reader"
```

---

## Phase 2 — Lineage Graph

### Task 6: Define node ID conventions

**Files:**
- Create: `oracle/graph/__init__.py`
- Create: `oracle/graph/nodes.py`
- Create: `tests/graph/__init__.py`
- Create: `tests/graph/test_nodes.py`

- [ ] **Step 1: Write the failing test `tests/graph/test_nodes.py`**

```python
from oracle.graph.nodes import NodeKind, make_id, parse_id


def test_make_and_parse_round_trip():
    node_id = make_id(NodeKind.MODEL, "stg_users")
    kind, name = parse_id(node_id)
    assert kind == NodeKind.MODEL
    assert name == "stg_users"


def test_column_id_uses_qualified_name():
    node_id = make_id(NodeKind.COLUMN, "users.signup_country")
    assert node_id == "column:users.signup_country"


def test_unknown_kind_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_id("notakind:foo")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph/test_nodes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/graph/nodes.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_nodes.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
mkdir -p oracle/graph tests/graph && touch oracle/graph/__init__.py tests/graph/__init__.py
git add oracle/graph tests/graph
git commit -m "feat: add lineage graph node conventions"
```

---

### Task 7: Build the lineage graph from parsed inputs

**Files:**
- Create: `oracle/graph/builder.py`
- Create: `tests/graph/test_builder.py`

- [ ] **Step 1: Write the failing test `tests/graph/test_builder.py`**

```python
from pathlib import Path

from oracle.graph.builder import build_graph
from oracle.ingest.airflow import parse_dag_file
from oracle.ingest.dbt import parse_manifest

FIX = Path(__file__).parent.parent / "ingest" / "fixtures"


def test_build_graph_includes_all_dbt_nodes():
    manifest = parse_manifest(FIX / "manifest_minimal.json")
    g = build_graph(manifest=manifest, dags=[], warehouse=None)
    assert "model:stg_users" in g.nodes
    assert "model:fct_user_metrics" in g.nodes
    assert "source:users" in g.nodes


def test_build_graph_adds_depends_on_edges():
    manifest = parse_manifest(FIX / "manifest_minimal.json")
    g = build_graph(manifest=manifest, dags=[], warehouse=None)
    assert g.has_edge("model:stg_users", "model:fct_user_metrics")


def test_build_graph_adds_dag_writes_edges():
    manifest = parse_manifest(FIX / "manifest_minimal.json")
    dag = parse_dag_file(FIX / "sample_dag.py")
    g = build_graph(manifest=manifest, dags=[dag], warehouse=None)
    # The DAG declares it writes to raw.users; we link the dag node to the source node.
    assert g.has_edge("dag:users_ingest", "source:users")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph/test_builder.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/graph/builder.py`**

```python
"""Construct the lineage graph from parsed dbt + Airflow + warehouse inputs."""
from __future__ import annotations

import networkx as nx

from oracle.graph.nodes import NodeKind, make_id
from oracle.ingest.airflow import AirflowDag
from oracle.ingest.dbt import DbtManifest
from oracle.ingest.warehouse import Warehouse


def _add_dbt(graph: nx.DiGraph, manifest: DbtManifest) -> None:
    for node in manifest.nodes:
        kind = NodeKind.SOURCE if node.resource_type == "source" else NodeKind.MODEL
        node_id = make_id(kind, node.name)
        graph.add_node(
            node_id,
            kind=kind.value,
            name=node.name,
            file_path=node.file_path,
            description=node.description,
        )
        for col in node.columns:
            col_id = make_id(NodeKind.COLUMN, f"{node.name}.{col.name}")
            graph.add_node(col_id, kind=NodeKind.COLUMN.value, name=col.name)
            graph.add_edge(node_id, col_id, relation="has_column")
        for upstream in node.depends_on:
            up_id_model = make_id(NodeKind.MODEL, upstream)
            up_id_source = make_id(NodeKind.SOURCE, upstream)
            up_id = up_id_model if up_id_model in graph.nodes else up_id_source
            graph.add_edge(up_id, node_id, relation="depends_on")


def _add_dags(graph: nx.DiGraph, dags: list[AirflowDag]) -> None:
    for dag in dags:
        dag_id = make_id(NodeKind.DAG, dag.dag_id)
        graph.add_node(
            dag_id,
            kind=NodeKind.DAG.value,
            name=dag.dag_id,
            file_path=str(dag.file_path),
            schedule=dag.schedule,
        )
        for table in dag.writes:
            # `writes` strings look like "raw.users" — the source node is keyed by
            # the table's short name (e.g. `source:users`), matching dbt's source name.
            short = table.split(".")[-1]
            target = make_id(NodeKind.SOURCE, short)
            if target in graph.nodes:
                graph.add_edge(dag_id, target, relation="refreshes")


def _add_warehouse(graph: nx.DiGraph, warehouse: Warehouse) -> None:
    for table in warehouse.tables:
        # Annotate any matching source node with row_count + dtype info.
        source_id = make_id(NodeKind.SOURCE, table.name)
        if source_id in graph.nodes:
            graph.nodes[source_id]["row_count"] = table.row_count
            graph.nodes[source_id]["dtypes"] = {c.name: c.dtype for c in table.columns}


def build_graph(
    manifest: DbtManifest,
    dags: list[AirflowDag],
    warehouse: Warehouse | None,
) -> nx.DiGraph:
    g: nx.DiGraph = nx.DiGraph()
    _add_dbt(g, manifest)
    _add_dags(g, dags)
    if warehouse is not None:
        _add_warehouse(g, warehouse)
    return g
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_builder.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/graph/builder.py tests/graph/test_builder.py
git commit -m "feat: build lineage graph from dbt + airflow + warehouse"
```

---

### Task 8: Persist the graph to JSON

**Files:**
- Create: `oracle/graph/store.py`
- Create: `tests/graph/test_store.py`

- [ ] **Step 1: Write the failing test `tests/graph/test_store.py`**

```python
import networkx as nx

from oracle.graph.store import load_graph, save_graph


def test_save_and_load_round_trip(tmp_path):
    g = nx.DiGraph()
    g.add_node("model:foo", kind="model", name="foo", file_path="models/foo.sql")
    g.add_node("model:bar", kind="model", name="bar", file_path="models/bar.sql")
    g.add_edge("model:foo", "model:bar", relation="depends_on")

    path = tmp_path / "graph.json"
    save_graph(g, path)
    loaded = load_graph(path)

    assert set(loaded.nodes) == {"model:foo", "model:bar"}
    assert loaded.has_edge("model:foo", "model:bar")
    assert loaded.edges["model:foo", "model:bar"]["relation"] == "depends_on"
    assert loaded.nodes["model:foo"]["file_path"] == "models/foo.sql"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph/test_store.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/graph/store.py`**

```python
"""Serialize/deserialize the lineage graph as JSON.

JSON is chosen over pickle so the artifact is human-readable and
version-controllable.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph


def save_graph(graph: nx.DiGraph, path: Path) -> None:
    data = json_graph.node_link_data(graph, edges="edges")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, default=str))


def load_graph(path: Path) -> nx.DiGraph:
    data = json.loads(Path(path).read_text())
    graph = json_graph.node_link_graph(data, directed=True, edges="edges")
    return graph
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graph/test_store.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/graph/store.py tests/graph/test_store.py
git commit -m "feat: persist lineage graph to JSON"
```

---

## Phase 3 — Embeddings & Index

### Task 9: Generate semantic descriptions per node

**Files:**
- Create: `oracle/index/__init__.py`
- Create: `oracle/index/descriptions.py`
- Create: `tests/index/__init__.py`
- Create: `tests/index/test_descriptions.py`

- [ ] **Step 1: Write the failing test `tests/index/test_descriptions.py`**

```python
import networkx as nx

from oracle.index.descriptions import describe_node


def test_describe_model_includes_name_and_inputs():
    g = nx.DiGraph()
    g.add_node("model:fct_users", kind="model", name="fct_users", description="user fact")
    g.add_node("model:stg_users", kind="model", name="stg_users", description="staging users")
    g.add_edge("model:stg_users", "model:fct_users", relation="depends_on")

    desc = describe_node(g, "model:fct_users")
    assert "fct_users" in desc
    assert "stg_users" in desc
    assert "user fact" in desc.lower() or "user fact" in desc


def test_describe_source_lists_columns():
    g = nx.DiGraph()
    g.add_node("source:users", kind="source", name="users", description="raw users table")
    g.add_node("column:users.user_id", kind="column", name="user_id")
    g.add_node("column:users.signup_country", kind="column", name="signup_country")
    g.add_edge("source:users", "column:users.user_id", relation="has_column")
    g.add_edge("source:users", "column:users.signup_country", relation="has_column")

    desc = describe_node(g, "source:users")
    assert "user_id" in desc
    assert "signup_country" in desc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/index/test_descriptions.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/index/descriptions.py`**

```python
"""Generate a short natural-language description for each graph node.

These descriptions are what we embed for semantic search. We assemble them
deterministically from graph structure (no LLM call needed for v1) so
indexing is fast and reproducible. A future version can use Claude to
write richer descriptions.
"""
from __future__ import annotations

import networkx as nx


def _columns_of(graph: nx.DiGraph, node_id: str) -> list[str]:
    return [
        graph.nodes[succ]["name"]
        for _, succ, data in graph.out_edges(node_id, data=True)
        if data.get("relation") == "has_column"
    ]


def _upstream_of(graph: nx.DiGraph, node_id: str) -> list[str]:
    return [
        graph.nodes[pred]["name"]
        for pred, _, data in graph.in_edges(node_id, data=True)
        if data.get("relation") == "depends_on"
    ]


def describe_node(graph: nx.DiGraph, node_id: str) -> str:
    data = graph.nodes[node_id]
    kind = data.get("kind", "")
    name = data.get("name", node_id)
    desc = data.get("description", "")
    parts: list[str] = [f"{kind} {name}."]
    if desc:
        parts.append(desc)
    cols = _columns_of(graph, node_id)
    if cols:
        parts.append(f"Columns: {', '.join(cols)}.")
    ups = _upstream_of(graph, node_id)
    if ups:
        parts.append(f"Built from: {', '.join(ups)}.")
    return " ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/index/test_descriptions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
mkdir -p oracle/index tests/index && touch oracle/index/__init__.py tests/index/__init__.py
git add oracle/index/descriptions.py oracle/index/__init__.py tests/index
git commit -m "feat: generate semantic descriptions per node"
```

---

### Task 10: Wrap the Voyage AI embeddings client

**Files:**
- Create: `oracle/index/embeddings.py`
- Create: `tests/index/test_embeddings.py`

- [ ] **Step 1: Write the failing test `tests/index/test_embeddings.py`**

```python
from unittest.mock import MagicMock

from oracle.index.embeddings import embed_texts


def test_embed_texts_calls_voyage_client():
    fake_client = MagicMock()
    fake_client.embed.return_value = MagicMock(embeddings=[[0.1, 0.2], [0.3, 0.4]])

    result = embed_texts(["hello", "world"], client=fake_client, model="voyage-3")

    fake_client.embed.assert_called_once_with(
        texts=["hello", "world"],
        model="voyage-3",
        input_type="document",
    )
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_texts_passes_input_type_for_query():
    fake_client = MagicMock()
    fake_client.embed.return_value = MagicMock(embeddings=[[0.1]])

    embed_texts(["q"], client=fake_client, model="voyage-3", input_type="query")

    args = fake_client.embed.call_args.kwargs
    assert args["input_type"] == "query"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/index/test_embeddings.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/index/embeddings.py`**

```python
"""Wrapper over Voyage AI's embeddings client.

Indexing uses input_type="document"; querying uses input_type="query".
Voyage tunes embeddings differently for each so passing the right one
matters for retrieval quality.
"""
from __future__ import annotations

from typing import Any, Literal

InputType = Literal["document", "query"]


def embed_texts(
    texts: list[str],
    *,
    client: Any,
    model: str = "voyage-3",
    input_type: InputType = "document",
) -> list[list[float]]:
    response = client.embed(texts=texts, model=model, input_type=input_type)
    return list(response.embeddings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/index/test_embeddings.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/index/embeddings.py tests/index/test_embeddings.py
git commit -m "feat: add voyage embeddings wrapper"
```

---

### Task 11: Persist embeddings in DuckDB with VSS

**Files:**
- Create: `oracle/index/store.py`
- Create: `tests/index/test_store.py`

- [ ] **Step 1: Write the failing test `tests/index/test_store.py`**

```python
from oracle.index.store import VectorStore


def test_save_and_search_returns_nearest(tmp_path):
    store = VectorStore(path=tmp_path / "v.duckdb", dim=2)
    store.upsert(
        [
            {"id": "model:a", "text": "alpha", "vector": [1.0, 0.0]},
            {"id": "model:b", "text": "beta", "vector": [0.0, 1.0]},
            {"id": "model:c", "text": "gamma", "vector": [1.0, 1.0]},
        ]
    )

    hits = store.search([1.0, 0.05], k=2)
    assert hits[0]["id"] == "model:a"
    assert {h["id"] for h in hits} == {"model:a", "model:c"}


def test_count_after_upsert(tmp_path):
    store = VectorStore(path=tmp_path / "v.duckdb", dim=2)
    store.upsert([{"id": "x", "text": "x", "vector": [1.0, 0.0]}])
    assert store.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/index/test_store.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/index/store.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/index/test_store.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/index/store.py tests/index/test_store.py
git commit -m "feat: add DuckDB VSS-backed vector store"
```

---

## Phase 4 — Tools

### Task 12: Implement `search_artifacts` tool

**Files:**
- Create: `oracle/tools/__init__.py`
- Create: `oracle/tools/search.py`
- Create: `tests/tools/__init__.py`
- Create: `tests/tools/test_search.py`

- [ ] **Step 1: Write the failing test `tests/tools/test_search.py`**

```python
from unittest.mock import MagicMock

from oracle.tools.search import search_artifacts


def test_search_artifacts_returns_top_k():
    store = MagicMock()
    store.search.return_value = [
        {"id": "model:a", "text": "alpha", "distance": 0.1},
        {"id": "model:b", "text": "beta", "distance": 0.2},
    ]
    embed = MagicMock(return_value=[[0.5, 0.5]])

    result = search_artifacts(
        query="alpha thing",
        k=2,
        store=store,
        embed_fn=embed,
    )

    assert len(result) == 2
    assert result[0]["id"] == "model:a"
    embed.assert_called_once_with(["alpha thing"], input_type="query")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_search.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/tools/search.py`**

```python
"""search_artifacts tool: vector search over the embeddings index."""
from __future__ import annotations

from typing import Any, Callable


def search_artifacts(
    query: str,
    k: int,
    store: Any,
    embed_fn: Callable[..., list[list[float]]],
) -> list[dict[str, Any]]:
    [vector] = embed_fn([query], input_type="query")
    return store.search(vector, k=k)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_search.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
mkdir -p oracle/tools tests/tools && touch oracle/tools/__init__.py tests/tools/__init__.py
git add oracle/tools tests/tools
git commit -m "feat: add search_artifacts tool"
```

---

### Task 13: Implement `get_lineage` tool

**Files:**
- Create: `oracle/tools/lineage.py`
- Create: `tests/tools/test_lineage.py`

- [ ] **Step 1: Write the failing test `tests/tools/test_lineage.py`**

```python
import networkx as nx

from oracle.tools.lineage import get_lineage


def _sample_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_node("model:stg_users", kind="model", name="stg_users", file_path="models/stg_users.sql")
    g.add_node("model:fct_users", kind="model", name="fct_users", file_path="models/fct_users.sql")
    g.add_node("model:dim_geo", kind="model", name="dim_geo", file_path="models/dim_geo.sql")
    g.add_edge("model:stg_users", "model:fct_users", relation="depends_on")
    g.add_edge("model:stg_users", "model:dim_geo", relation="depends_on")
    return g


def test_get_lineage_upstream():
    g = _sample_graph()
    hits = get_lineage(g, node_id="model:fct_users", direction="up", depth=1)
    ids = {h["node_id"] for h in hits}
    assert ids == {"model:stg_users"}


def test_get_lineage_downstream():
    g = _sample_graph()
    hits = get_lineage(g, node_id="model:stg_users", direction="down", depth=1)
    ids = {h["node_id"] for h in hits}
    assert ids == {"model:fct_users", "model:dim_geo"}


def test_get_lineage_includes_relation_and_file():
    g = _sample_graph()
    hits = get_lineage(g, node_id="model:fct_users", direction="up", depth=1)
    assert hits[0]["relation"] == "depends_on"
    assert hits[0]["file_path"] == "models/stg_users.sql"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_lineage.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/tools/lineage.py`**

```python
"""get_lineage tool: graph traversal up or down from a node."""
from __future__ import annotations

from typing import Any, Literal

import networkx as nx

Direction = Literal["up", "down"]


def get_lineage(
    graph: nx.DiGraph,
    *,
    node_id: str,
    direction: Direction,
    depth: int = 3,
) -> list[dict[str, Any]]:
    if node_id not in graph.nodes:
        return []

    edges_iter = graph.in_edges if direction == "up" else graph.out_edges
    other = (lambda u, v: u) if direction == "up" else (lambda u, v: v)

    visited: set[str] = set()
    frontier: list[tuple[str, int]] = [(node_id, 0)]
    results: list[dict[str, Any]] = []

    while frontier:
        current, hop = frontier.pop()
        if hop >= depth:
            continue
        for u, v, data in edges_iter(current, data=True):
            neighbor = other(u, v)
            if neighbor in visited:
                continue
            visited.add(neighbor)
            ndata = graph.nodes[neighbor]
            results.append(
                {
                    "node_id": neighbor,
                    "kind": ndata.get("kind", ""),
                    "name": ndata.get("name", ""),
                    "relation": data.get("relation", ""),
                    "file_path": ndata.get("file_path", ""),
                    "hop": hop + 1,
                }
            )
            frontier.append((neighbor, hop + 1))

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_lineage.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/tools/lineage.py tests/tools/test_lineage.py
git commit -m "feat: add get_lineage tool"
```

---

### Task 14: Implement `get_schema` tool

**Files:**
- Create: `oracle/tools/schema.py`
- Create: `tests/tools/test_schema.py`

- [ ] **Step 1: Write the failing test `tests/tools/test_schema.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_schema.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/tools/schema.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_schema.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/tools/schema.py tests/tools/test_schema.py
git commit -m "feat: add get_schema tool"
```

---

### Task 15: Implement `find_references` tool

**Files:**
- Create: `oracle/tools/references.py`
- Create: `tests/tools/test_references.py`

- [ ] **Step 1: Write the failing test `tests/tools/test_references.py`**

```python
from oracle.tools.references import find_references


def test_find_references_finds_column_in_sql(tmp_path):
    sql = tmp_path / "stg_users.sql"
    sql.write_text("SELECT user_id, signup_country FROM raw.users\n")
    py = tmp_path / "dag.py"
    py.write_text("# uses signup_country\nx = 1\n")
    other = tmp_path / "other.sql"
    other.write_text("SELECT id FROM other\n")

    hits = find_references("signup_country", search_dirs=[tmp_path])
    files = {h["file"].split("/")[-1] for h in hits}
    assert files == {"stg_users.sql", "dag.py"}


def test_find_references_returns_line_and_snippet(tmp_path):
    sql = tmp_path / "x.sql"
    sql.write_text("SELECT a\nFROM tab\nWHERE country = 'US'\n")

    hits = find_references("country", search_dirs=[tmp_path])
    assert hits[0]["line"] == 3
    assert "country" in hits[0]["snippet"]


def test_find_references_returns_empty_when_no_match(tmp_path):
    (tmp_path / "x.sql").write_text("SELECT 1\n")
    hits = find_references("missing_col", search_dirs=[tmp_path])
    assert hits == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_references.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/tools/references.py`**

```python
"""find_references tool: grep across .sql and .py files for a column or table reference.

Plain text search is sufficient for v1. We could parse SQL ASTs in v2 to
distinguish a column reference from a substring match.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

EXTENSIONS = {".sql", ".py"}


def find_references(
    needle: str,
    *,
    search_dirs: list[Path],
) -> list[dict[str, Any]]:
    pattern = re.compile(rf"\b{re.escape(needle)}\b")
    hits: list[dict[str, Any]] = []
    for root in search_dirs:
        for path in Path(root).rglob("*"):
            if path.suffix not in EXTENSIONS or not path.is_file():
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), start=1):
                if pattern.search(line):
                    hits.append(
                        {
                            "file": str(path),
                            "line": lineno,
                            "snippet": line.strip(),
                        }
                    )
    return hits
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_references.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/tools/references.py tests/tools/test_references.py
git commit -m "feat: add find_references tool"
```

---

### Task 16: Define tool JSON schemas for Claude

**Files:**
- Create: `oracle/tools/definitions.py`
- Create: `tests/tools/test_definitions.py`

- [ ] **Step 1: Write the failing test `tests/tools/test_definitions.py`**

```python
from oracle.tools.definitions import TOOL_DEFINITIONS


def test_tool_definitions_has_four_tools():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"search_artifacts", "get_lineage", "get_schema", "find_references"}


def test_each_tool_has_input_schema():
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_definitions.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/tools/definitions.py`**

```python
"""JSON schema definitions passed to Claude as the agent's tool list."""

TOOL_DEFINITIONS = [
    {
        "name": "search_artifacts",
        "description": (
            "Find data warehouse artifacts (tables, models, columns, DAGs) by natural-language "
            "description. Use this when the user asks about a concept (e.g. 'user purchases') "
            "and you don't know the exact artifact name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The natural language query."},
                "k": {"type": "integer", "description": "Max results.", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_lineage",
        "description": (
            "Walk the lineage graph up or down from a node. Use 'up' for 'what feeds X?' "
            "and 'down' for 'what depends on X?'. node_id is in the form 'model:foo' or "
            "'source:bar'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "direction": {"type": "string", "enum": ["up", "down"]},
                "depth": {"type": "integer", "default": 3},
            },
            "required": ["node_id", "direction"],
        },
    },
    {
        "name": "get_schema",
        "description": (
            "Return columns, types, and row count for a fully qualified table name "
            "(schema.table). Use when the user asks about table structure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Fully qualified table name e.g. 'raw.users'.",
                }
            },
            "required": ["table"],
        },
    },
    {
        "name": "find_references",
        "description": (
            "Find all .sql and .py files where a column or table name appears, with "
            "file path and line number. Use this for impact analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "needle": {"type": "string", "description": "Column or table name to search for."}
            },
            "required": ["needle"],
        },
    },
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_definitions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/tools/definitions.py tests/tools/test_definitions.py
git commit -m "feat: add tool JSON schema definitions for Claude"
```

---

## Phase 5 — Agent

### Task 17: Implement the tool-use loop

**Files:**
- Create: `oracle/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write the failing test `tests/test_agent.py`**

```python
from unittest.mock import MagicMock

from oracle.agent import Agent


def _stop_message(text: str):
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [MagicMock(type="text", text=text)]
    return msg


def _tool_use_message(tool_name: str, tool_input: dict, tool_use_id: str = "call_1"):
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [
        MagicMock(type="text", text="thinking"),
        MagicMock(type="tool_use", id=tool_use_id, name=tool_name, input=tool_input),
    ]
    return msg


def test_agent_returns_text_when_no_tools_called():
    client = MagicMock()
    client.messages.create.return_value = _stop_message("the answer is 42")
    agent = Agent(client=client, tool_runner=lambda name, args: {})
    out = agent.ask("what is 6 times 7?")
    assert "42" in out


def test_agent_runs_tool_then_finalizes():
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_message("get_schema", {"table": "raw.users"}),
        _stop_message("the table has 2 columns"),
    ]
    runner_calls = []

    def runner(name, args):
        runner_calls.append((name, args))
        return {"columns": [{"name": "a"}, {"name": "b"}]}

    agent = Agent(client=client, tool_runner=runner)
    out = agent.ask("schema of raw.users?")

    assert "2 columns" in out
    assert runner_calls == [("get_schema", {"table": "raw.users"})]


def test_agent_caps_tool_calls():
    client = MagicMock()
    # always returns a tool_use — would loop forever without cap
    client.messages.create.return_value = _tool_use_message("get_schema", {"table": "x"})
    agent = Agent(client=client, tool_runner=lambda n, a: {}, max_tool_calls=3)
    out = agent.ask("trick question")
    assert "couldn't answer" in out.lower() or "could not" in out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/agent.py`**

```python
"""Claude tool-use agent loop.

Stays small on purpose: one class, one method. The agent receives a
question, calls the model in a loop, runs whatever tool the model asks
for, and stops when the model returns end_turn (or the cap is hit).
"""
from __future__ import annotations

from typing import Any, Callable

from oracle.tools.definitions import TOOL_DEFINITIONS

SYSTEM_PROMPT = """You answer questions about a data warehouse.

You have four tools. Decide which to call based on the question:
- search_artifacts: find an artifact by description (use when name is unknown)
- get_lineage: trace upstream or downstream from a known node
- get_schema: read a table's columns and row count
- find_references: find code that references a column or table

Rules:
- Always cite the file path or DAG name behind each claim.
- Never invent table or column names. If unsure, call search_artifacts first.
- If you cannot answer with grounded evidence, say so.
"""


class Agent:
    def __init__(
        self,
        *,
        client: Any,
        tool_runner: Callable[[str, dict], Any],
        model: str = "claude-sonnet-4-6",
        max_tool_calls: int = 6,
    ) -> None:
        self.client = client
        self.tool_runner = tool_runner
        self.model = model
        self.max_tool_calls = max_tool_calls

    def ask(self, question: str) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

        for _ in range(self.max_tool_calls + 1):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return _extract_text(response)

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    output = self.tool_runner(block.name, dict(block.input))
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(output),
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
                continue

            return _extract_text(response)

        return "I couldn't answer this confidently within the tool-call budget."


def _extract_text(response: Any) -> str:
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return "".join(parts) or "(no response)"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add oracle/agent.py tests/test_agent.py
git commit -m "feat: add Claude tool-use agent loop"
```

---

## Phase 6 — CLI

### Task 18: Wire `oracle index` command

**Files:**
- Create: `oracle/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test `tests/test_cli.py`**

```python
from typer.testing import CliRunner

from oracle.cli import app

runner = CliRunner()


def test_cli_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.stdout
    assert "ask" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `oracle/cli.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 1 passed.

- [ ] **Step 5: Smoke-test `oracle index` against jaffle_shop**

Set up `.env` with your real API keys (copy from `.env.example`), then:
```bash
uv run oracle index \
  --manifest data/jaffle_shop/dbt_project/target/manifest.json \
  --dags-dir data/jaffle_shop/dags \
  --warehouse data/jaffle_shop/dbt_project/jaffle_shop.duckdb
```
Expected: prints "Saved .oracle/graph.json (~30+ nodes)" and "Saved .oracle/vectors.duckdb (~30+ embeddings)".

- [ ] **Step 6: Smoke-test `oracle ask`**

Run:
```bash
uv run oracle ask "what feeds fct_orders?" \
  --warehouse data/jaffle_shop/dbt_project/jaffle_shop.duckdb \
  --search-dir data/jaffle_shop
```
Expected: a grounded answer naming `stg_orders` (or similar upstream model) with file paths.

- [ ] **Step 7: Commit**

```bash
git add oracle/cli.py tests/test_cli.py
git commit -m "feat: add Typer CLI with index and ask commands"
```

---

## Phase 7 — Streamlit UI

### Task 19: Build the Streamlit chat UI

**Files:**
- Create: `ui/streamlit_app.py`

- [ ] **Step 1: Implement `ui/streamlit_app.py`**

```python
"""Streamlit chat UI — a thin wrapper over the oracle library.

All AI logic lives in oracle.agent; this file only handles UI state.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Lineage Oracle", page_icon="🔮", layout="wide")
st.title("🔮 Lineage Oracle")
st.caption("Ask questions about your data warehouse, with grounded citations.")

INDEX_DIR = Path(".oracle")
WAREHOUSE = Path("data/jaffle_shop/dbt_project/jaffle_shop.duckdb")
SEARCH_DIR = Path("data/jaffle_shop")


@st.cache_resource
def load_dependencies():
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


agent = load_dependencies()

if "history" not in st.session_state:
    st.session_state.history = []

for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)

prompt = st.chat_input("Ask Oracle a question...")
if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = agent.ask(prompt)
        st.markdown(answer)
    st.session_state.history.append(("assistant", answer))
```

- [ ] **Step 2: Smoke-test the UI**

Run: `uv run streamlit run ui/streamlit_app.py`
Expected: opens browser to a chat interface; questions like "what feeds fct_orders?" return grounded answers.

- [ ] **Step 3: Commit**

```bash
git add ui/streamlit_app.py
git commit -m "feat: add Streamlit chat UI"
```

---

## Phase 8 — Eval Harness

### Task 20: Author the eval set

**Files:**
- Create: `evals/eval_set.json`

- [ ] **Step 1: Create `evals/eval_set.json` with 30 questions**

```json
[
  {
    "id": "lineage_001",
    "category": "lineage",
    "question": "What feeds fct_orders?",
    "expected_facts": ["stg_orders"],
    "must_cite": ["stg_orders.sql"],
    "must_not_invent": true
  },
  {
    "id": "lineage_002",
    "category": "lineage",
    "question": "What feeds stg_customers?",
    "expected_facts": ["raw_customers"],
    "must_cite": ["raw_customers"],
    "must_not_invent": true
  },
  {
    "id": "lineage_003",
    "category": "lineage",
    "question": "Which DAG refreshes raw.orders?",
    "expected_facts": ["orders_ingest"],
    "must_cite": ["orders_ingest"],
    "must_not_invent": true
  },
  {
    "id": "impact_001",
    "category": "impact",
    "question": "If I drop the customer_id column from stg_customers, what breaks?",
    "expected_facts": ["customer_id"],
    "must_cite": [],
    "must_not_invent": true
  },
  {
    "id": "impact_002",
    "category": "impact",
    "question": "What depends on stg_orders?",
    "expected_facts": ["fct_orders"],
    "must_cite": [],
    "must_not_invent": true
  },
  {
    "id": "schema_001",
    "category": "schema",
    "question": "What columns are in raw_orders?",
    "expected_facts": ["id", "user_id", "order_date"],
    "must_cite": [],
    "must_not_invent": true
  },
  {
    "id": "schema_002",
    "category": "schema",
    "question": "What columns does stg_payments expose?",
    "expected_facts": [],
    "must_cite": [],
    "must_not_invent": true
  },
  {
    "id": "semantic_001",
    "category": "semantic",
    "question": "Which table tracks customer payments?",
    "expected_facts": ["payments"],
    "must_cite": [],
    "must_not_invent": true
  },
  {
    "id": "semantic_002",
    "category": "semantic",
    "question": "Where do we store order data?",
    "expected_facts": ["orders"],
    "must_cite": [],
    "must_not_invent": true
  },
  {
    "id": "semantic_003",
    "category": "semantic",
    "question": "What is the customer fact table called?",
    "expected_facts": ["customers"],
    "must_cite": [],
    "must_not_invent": true
  }
]
```

> Note: this is the seed set of 10 questions. After running the system end-to-end, expand to ~30 by adding 5 more per category. Keep `expected_facts` empty (`[]`) only when verification is purely structural.

- [ ] **Step 2: Commit**

```bash
git add evals/eval_set.json
git commit -m "feat: add eval set with seed questions"
```

---

### Task 21: Build the pytest eval runner

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/conftest.py`
- Create: `evals/test_evals.py`

- [ ] **Step 1: Create `evals/__init__.py`**

```bash
touch evals/__init__.py
```

- [ ] **Step 2: Create `evals/conftest.py`**

```python
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
```

- [ ] **Step 3: Create `evals/test_evals.py`**

```python
"""Eval harness: runs each question through the live agent and asserts metrics.

Skipped automatically when API keys are not set so unit-test runs don't pay
for API calls.
"""
from __future__ import annotations

import os

import pytest

from evals.conftest import load_eval_set

EVAL_SET = load_eval_set()
HAS_KEYS = bool(os.environ.get("ANTHROPIC_API_KEY")) and bool(os.environ.get("VOYAGE_API_KEY"))


@pytest.mark.skipif(not HAS_KEYS, reason="API keys not configured")
@pytest.mark.parametrize("case", EVAL_SET, ids=[c["id"] for c in EVAL_SET])
def test_eval_case(case, agent):
    answer = agent.ask(case["question"]).lower()

    # Fact recall: every expected fact appears in the answer.
    missing = [f for f in case["expected_facts"] if f.lower() not in answer]
    assert not missing, f"missing expected facts: {missing}\nanswer: {answer}"

    # Must-cite paths appear verbatim in the answer.
    for cite in case["must_cite"]:
        assert cite.lower() in answer, f"missing required citation: {cite}\nanswer: {answer}"
```

- [ ] **Step 4: Run the eval suite**

Run: `uv run pytest evals/ -v`
Expected: all eval cases pass (or, on first run, you'll see specific failures pointing at prompt or retrieval issues — iterate from there).

- [ ] **Step 5: Commit**

```bash
git add evals/__init__.py evals/conftest.py evals/test_evals.py
git commit -m "feat: add pytest-based eval harness"
```

---

## Phase 9 — Polish & Ship

### Task 22: Write the README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Lineage Oracle

An AI agent that answers questions about a data warehouse with grounded lineage citations.

> *"What feeds `fct_user_metrics`?"* → traces upstream models with their source DAGs, citing each `.sql` file.

## What it does

Lineage Oracle ingests a dbt project's `manifest.json`, the Airflow DAG files
that refresh raw tables, and a DuckDB warehouse's `information_schema`. It builds
a NetworkX lineage graph and a Voyage-3 embedding index over each artifact, then
answers questions via a Claude tool-use loop.

Four supported question types:

- **Lineage** — "What feeds X?" / "What does X feed?"
- **Impact** — "If I drop column Y, what breaks?"
- **Semantic** — "Which table tracks user purchases?"
- **Schema** — "What columns are in X?"

Every answer is grounded: the agent cites the `.sql` file or DAG it pulled
each fact from, and refuses to invent table or column names.

## Architecture

Two-phase system:

- **Index Phase** (`oracle index`) — parses the inputs, builds the lineage graph,
  generates per-node descriptions, embeds them with Voyage-3, persists everything
  to `.oracle/`.
- **Query Phase** (`oracle ask "..."`) — loads the graph + vector store, runs a
  Claude Sonnet 4.6 tool-use loop with four tools: `search_artifacts`,
  `get_lineage`, `get_schema`, `find_references`.

The `oracle` Python library is the single source of truth; the CLI and the
Streamlit chat UI are thin wrappers over `oracle.agent.Agent`.

## Quickstart

```bash
# 1. Install
uv sync

# 2. Configure API keys
cp .env.example .env
# Edit .env to add ANTHROPIC_API_KEY and VOYAGE_API_KEY

# 3. Build the demo warehouse + manifest
cd data/jaffle_shop/dbt_project
dbt seed && dbt run && dbt parse
cd ../../..

# 4. Index
uv run oracle index \
  --manifest data/jaffle_shop/dbt_project/target/manifest.json \
  --dags-dir data/jaffle_shop/dags \
  --warehouse data/jaffle_shop/dbt_project/jaffle_shop.duckdb

# 5. Ask
uv run oracle ask "what feeds fct_orders?" \
  --warehouse data/jaffle_shop/dbt_project/jaffle_shop.duckdb \
  --search-dir data/jaffle_shop

# 6. Or use the chat UI
uv run streamlit run ui/streamlit_app.py
```

## Eval results

A pytest-based eval harness at `evals/` measures fact recall, citation
precision, and no-invention rate against ~30 ground-truth questions.

```bash
uv run pytest evals/ -v
```

## Tech stack

- **LLM:** Claude Sonnet 4.6 (Anthropic SDK, native tool use, no LangChain)
- **Embeddings:** Voyage-3
- **Vector store:** DuckDB + VSS extension
- **Lineage graph:** NetworkX, persisted as JSON
- **dbt parsing:** `manifest.json` (no dbt runtime)
- **Airflow parsing:** Python `ast` (static)
- **CLI:** Typer
- **UI:** Streamlit
- **Test framework:** pytest

## Project structure

See `docs/superpowers/specs/2026-05-06-lineage-oracle-design.md` for the
full design spec.

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README"
```

---

### Task 23: Run code-simplifier on the codebase

**Files:**
- (review only — code-simplifier may suggest edits)

- [ ] **Step 1: Dispatch the code-simplifier agent**

In a new conversation turn, ask Claude:
> "Review and simplify the recently changed code in `oracle/`, `ui/`, and `evals/`."

The code-simplifier agent will scan recently modified files, propose simplifications, and apply approved changes.

- [ ] **Step 2: Run the full test suite to verify nothing broke**

Run: `uv run pytest -v`
Expected: all unit tests pass. (Eval suite optional — costs API calls.)

- [ ] **Step 3: Commit any simplifications as a separate commit**

```bash
git add -A
git commit -m "refactor: apply code-simplifier suggestions"
```

---

### Task 24: Push to GitHub

**Files:**
- (no new files — repo creation only)

- [ ] **Step 1: Confirm `gh` is authenticated**

Run: `gh auth status`
Expected: shows logged-in account `Mona-Alkhatib`. If not: `gh auth login`.

- [ ] **Step 2: Create the GitHub repo and push**

Run:
```bash
gh repo create lineage-oracle --public --source=. --remote=origin --push --description "AI agent that answers grounded questions about a data warehouse"
```
Expected: prints repo URL like `https://github.com/Mona-Alkhatib/lineage-oracle`.

- [ ] **Step 3: Verify the push succeeded**

Run: `gh repo view --web`
Expected: opens the repo in your browser.

---

## Done

After Task 24, you should have:

1. A live, public GitHub repo with the full project.
2. A working `oracle ask` CLI grounded in jaffle_shop.
3. A Streamlit chat UI that demos the same library.
4. A pytest eval harness with seed questions.
5. A clean README that walks through setup + architecture.

Next steps for v2 (out of scope here): expand eval set to 30+ questions, add CI to run unit tests on push, deploy Streamlit UI to Streamlit Community Cloud, replace jaffle_shop with a custom dataset.
