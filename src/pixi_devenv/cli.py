from pathlib import Path

from typer import Typer, Exit
import rich

from pixi_devenv.error import DevEnvError
from pixi_devenv.update import update_pixi_config
from pixi_devenv.init import init_devenv

app = Typer()


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


@app.command()
def import_from_conda(file: str = "environment.devenv.yml", feature: str = "") -> None:
    """Import conda-devenv configuration into a pixi.devenv.toml file"""
    # 'feature' is used to import the environment.devenv.yml contents as a feature.
    print(f"Coming soon ({file} {feature})")
