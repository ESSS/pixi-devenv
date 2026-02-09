from pathlib import Path
import importlib.metadata
from typing import Annotated

from typer import Typer, Exit, Option
import rich

from pixi_devenv.error import DevEnvError
from pixi_devenv.update import update_pixi_config
from pixi_devenv.init import init_devenv

app = Typer()


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[bool, Option("--version", is_eager=True)] = False,
) -> None:
    """Placeholder that implements --version."""
    if version:
        version_str = importlib.metadata.version("pixi-devenv")
        print(f"pixi-devenv {version_str}")
        raise Exit()


@app.command()
def update(path: Path | None = None) -> None:
    """Update pixi configuration in the given directory (defaults to cwd)"""
    updated = update_pixi_config(path or Path.cwd())
    if updated:
        rich.print("[green]pixi configuration updated[/green]")
    else:
        rich.print("pixi configuration already up to date")


@app.command()
def init() -> None:
    """Initialize pixi-devenv configuration in this directory."""
    try:
        init_devenv(Path.cwd())
    except DevEnvError as e:
        rich.print(f"[red]ERROR: {e}[/red]")
        raise Exit(code=1)
    else:
        rich.print(
            "[green]pixi devenv initialized. Edit pixi.devenv.toml as needed and run 'pixi update'.[/green]"
        )
