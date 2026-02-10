from typer.testing import CliRunner

from pixi_devenv.cli import app


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("pixi-devenv ")
