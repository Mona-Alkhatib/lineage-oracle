from typer.testing import CliRunner

from oracle.cli import app

runner = CliRunner()


def test_cli_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.stdout
    assert "ask" in result.stdout
