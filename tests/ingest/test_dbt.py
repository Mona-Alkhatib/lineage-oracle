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
