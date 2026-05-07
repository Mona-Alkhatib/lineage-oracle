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
