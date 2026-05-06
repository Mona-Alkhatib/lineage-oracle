# Lineage Oracle — Design Spec

**Date:** 2026-05-06
**Author:** Mona Alkhatib (with Claude Code)
**Status:** Approved (brainstorming → writing-plans)

---

## 1. Vision

**Lineage Oracle** is an AI agent that answers questions about a data warehouse with grounded lineage citations. Every claim in every answer is backed by a reference to the file, line, or DAG it came from — no hallucinated tables, no invented columns.

It is built to demonstrate AI engineering depth (retrieval-augmented agents, tool use, evals) on top of real data engineering substrate (dbt manifests, Airflow DAGs, warehouse metadata).

### Example interactions

- *"What feeds `fct_user_metrics`?"* → lists upstream models with their source DAGs.
- *"If I drop `users.signup_country`, what breaks?"* → enumerates downstream artifacts.
- *"Which table tracks user purchases?"* → semantic match against table descriptions.
- *"What columns are in `stg_orders`?"* → schema introspection.

---

## 2. Goals & non-goals

### Goals (v1)

1. Answer four classes of questions accurately on a real dbt + Airflow + warehouse setup:
   - Lineage queries (upstream / downstream)
   - Impact queries (column-level breakage analysis)
   - Semantic search (natural language → artifact)
   - Schema introspection
2. Ground every answer with citations (file path + line number).
3. Provide three usage modes: Python library, CLI, web UI — all backed by the same library.
4. Ship an eval harness that measures fact recall, citation precision, and no-invention guarantees on a held-out QA set.
5. Run end-to-end against the public **jaffle_shop** dbt project.

### Non-goals (v1)

- Freshness / SLA queries (no Airflow runtime integration).
- Performance / cost analysis ("which models are slowest").
- Free-form code Q&A ("explain this CTE").
- Cross-database lineage (single warehouse only).
- Multi-tenant or cloud deployment.

These belong to v2 or later.

---

## 3. Architecture

The system is split into three phases:

### 3.1 Index Phase

Runs once via `oracle index`. Re-runs when source files change.

**Inputs:**
- dbt project's `manifest.json`
- Airflow DAG `.py` files
- DuckDB warehouse `information_schema`

> Note: jaffle_shop ships with dbt models but not Airflow DAGs. We will hand-author 3–4 toy DAGs (one per source table) under `data/jaffle_shop/dags/` so the agent has real DAG inputs to reason about. These are static `.py` files — no Airflow runtime needed.

**Build steps:**
1. **Parse inputs**
   - dbt: walk `manifest.json` for nodes (models, sources, seeds), `depends_on`, column docs.
   - Airflow: static AST parse — extract DAG id, schedule, tasks, and what tables each task reads/writes (matched against known operator patterns).
   - Warehouse: query `information_schema.columns` for ground-truth schema.
2. **Build the lineage graph** (NetworkX `DiGraph`)
   - Node types: `source`, `model`, `column`, `dag`, `task`
   - Edge types: `depends_on`, `derived_from`, `refreshes`, `has_column`
3. **Generate semantic descriptions** — one short paragraph per node, written by Claude during indexing (cached, only regenerated on change).
4. **Embed descriptions** with `voyage-3` and store vectors in DuckDB using the VSS extension.

**Persisted outputs:**
- `.oracle/graph.json` — NetworkX graph serialized
- `.oracle/vectors.duckdb` — embeddings + HNSW index
- `.oracle/metadata.json` — source-file hashes for incremental re-index

### 3.2 Query Phase

Runs on every user question.

**Flow:**
1. User question hits `oracle.ask(question)` (called by CLI or Streamlit).
2. Library loads graph + vector index (lazy, cached).
3. System prompt + question + tool definitions go to Claude Sonnet 4.6.
4. Claude executes a tool-use loop (capped at 6 iterations):
   - Call a tool → receive structured result → decide whether to call another or compose final answer.
5. Final answer returned with structured citations.

**Tools** (4 total — see §4 for detail):
- `search_artifacts(query, k)`
- `get_lineage(node, direction, depth)`
- `get_schema(table)`
- `find_references(column)`

**Citations:** every factual claim in the answer must be tagged with the artifact it came from. The agent is instructed to refuse if it cannot ground a claim.

### 3.3 Eval Harness

Runs on every change.

**Format** — `evals/eval_set.json`:
```json
{
  "id": "lineage_001",
  "question": "What feeds fct_user_metrics?",
  "expected_facts": ["stg_users", "stg_orders"],
  "must_cite": ["models/marts/fct_user_metrics.sql"],
  "must_not_invent": true
}
```

**Metrics:**
- **Fact recall** — fraction of `expected_facts` present in the answer.
- **Citation precision** — fraction of cited paths that actually exist on disk.
- **No-invention rate** — fraction of mentioned tables/columns that exist in the warehouse.

**Runner:** `pytest evals/` — each question is a parametrized case. CI fails if any metric drops below threshold (initial threshold: 0.85 for recall, 1.00 for precision and no-invention).

---

## 4. Tools (agent contract)

### 4.1 `search_artifacts(query: str, k: int = 5)`

Vector similarity search over the embeddings index.

**Returns:** list of `{node_id, node_type, description, score}`.

**Used for:** "which table tracks user purchases?"

### 4.2 `get_lineage(node_id: str, direction: 'up' | 'down', depth: int = 3)`

Graph traversal from a node.

**Returns:** list of `{node_id, relation, hop, file, line}`.

**Used for:** "what feeds X?" / "what does X feed?"

### 4.3 `get_schema(table: str)`

Direct query against `information_schema`.

**Returns:** `{table, columns: [{name, type, nullable}], row_count}`.

**Used for:** "what columns are in X?"

### 4.4 `find_references(column: str, table: str | None = None)`

Grep across `.sql` and `.py` files for column references.

**Returns:** list of `{file, line, snippet, context}`.

**Used for:** "if I drop X, what breaks?"

---

## 5. Project structure

```
lineage-oracle/
├── oracle/                  # the library — single source of truth
│   ├── __init__.py
│   ├── ingest/
│   │   ├── dbt.py           # manifest.json walker
│   │   ├── airflow.py       # AST-based DAG parser
│   │   └── warehouse.py     # information_schema reader
│   ├── graph/
│   │   ├── builder.py       # constructs NetworkX graph from parsed inputs
│   │   └── store.py         # JSON serialization
│   ├── index/
│   │   ├── descriptions.py  # generate semantic descriptions (cached)
│   │   ├── embeddings.py    # voyage-3 client wrapper
│   │   └── store.py         # DuckDB VSS persistence
│   ├── tools/
│   │   ├── search.py
│   │   ├── lineage.py
│   │   ├── schema.py
│   │   └── references.py
│   ├── agent.py             # tool-use loop
│   └── cli.py               # Typer CLI
├── ui/
│   └── streamlit_app.py     # thin UI wrapper around oracle.ask()
├── data/
│   └── jaffle_shop/         # demo dbt project + toy DAGs
├── evals/
│   ├── eval_set.json
│   └── test_evals.py        # pytest runner
├── tests/                   # unit tests (mirror oracle/ layout)
├── pyproject.toml           # uv + ruff
├── .gitignore
└── README.md
```

---

## 6. Stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Matches data-eng ecosystem |
| LLM | Claude Sonnet 4.6 (Anthropic SDK) | Smart + fast + cheap for evals; prompt caching |
| Embeddings | voyage-3 | Anthropic's recommended pairing |
| Vector store | DuckDB + VSS | Same engine as warehouse — clean story |
| Graph | NetworkX (in-memory, JSON-persisted) | Sufficient for jaffle_shop scale |
| dbt parsing | manifest.json (no dbt runtime) | Faster, no env coupling |
| Airflow parsing | `ast` (static) | No Airflow runtime needed |
| CLI | Typer | Modern, type-driven |
| Web UI | Streamlit | One-file, Python-native, free deploy |
| Test framework | pytest | Standard |
| Package mgr | uv | Fast, modern; signals stays-current |
| Lint/format | ruff | Single-tool replacement for black + isort + flake8 |
| LLM framework | None (raw Anthropic SDK) | Defensible architectural choice; debuggable |

---

## 7. Error handling

- **Missing artifacts:** if a question references a node that doesn't exist, the agent calls `search_artifacts` to find the closest match and confirms with the user.
- **Tool failures:** tool errors are returned to Claude as `tool_result` content with `is_error: true`; the agent retries or surfaces the failure.
- **Tool-loop runaway:** hard cap of 6 tool calls per question. If reached without an answer, return "I couldn't answer this confidently."
- **Stale index:** on every `oracle.ask`, compare source-file hashes against `metadata.json`; warn the user if re-indexing is needed.
- **API failures (Claude / Voyage):** exponential backoff with 3 retries, then surface a clean error.

---

## 8. Testing strategy

### Unit tests (`tests/`)

- `ingest/`: parsing dbt manifest fixtures, AST parsing of sample DAGs, `information_schema` querying against a fixture DuckDB.
- `graph/`: graph building and JSON round-trip.
- `tools/`: each tool tested in isolation with stubbed graph + index.
- Target: ≥ 90% line coverage on `oracle/` (excluding `agent.py`).

### Integration tests

- End-to-end `oracle.ask()` against jaffle_shop with mocked Claude responses (deterministic).

### Eval harness (`evals/`)

- ~30 ground-truth questions across the four scope categories.
- Real Claude API calls (not mocked) so we catch prompt regressions.
- Run nightly + on every PR; fail CI on threshold drop.

---

## 9. Open questions / future work

- **Re-indexing on file watch:** v1 requires manual `oracle index`. v2 could watch dbt/airflow folders.
- **Web UI deployment:** v1 runs Streamlit locally. v2 deploys to Streamlit Community Cloud with a public demo URL.
- **Bring-your-own-warehouse:** v1 hardcodes DuckDB. v2 abstracts warehouse access (Snowflake, BigQuery, Trino).
- **Multi-tenant:** out of scope.
- **Custom dataset (replace jaffle_shop):** planned for v2 once core works.

---

## 10. Success criteria for v1

The project is "shippable to portfolio" when:

1. `uv sync && oracle index && oracle ask "what feeds fct_orders?"` works from a fresh clone.
2. Streamlit UI loads, accepts a question, returns answer with clickable citations.
3. `pytest evals/` passes with ≥ 0.85 fact recall and 1.00 citation precision.
4. README walks through architecture, demo, and eval results.
5. Repo deployed to https://github.com/Mona-Alkhatib/lineage-oracle.
