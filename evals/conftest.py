"""Shared fixtures for the eval harness."""
from __future__ import annotations

import json
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
    from oracle.runtime import build_agent

    agent, _vstore = build_agent(
        index_dir=INDEX_DIR,
        warehouse_path=WAREHOUSE,
        search_dir=SEARCH_DIR,
    )
    return agent
