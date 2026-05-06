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
