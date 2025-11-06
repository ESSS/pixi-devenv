from pathlib import Path

from typer import Typer
import rich

from pixi_devenv.update import update_pixi_config

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
    """Initialize pixi-devenv configuration in this directory (TODO)"""
    print("Coming soon")


@app.command()
def import_from_conda(file: str = "environment.devenv.yml", feature: str = "") -> None:
    """Import conda-devenv configuration into a pixi.devenv.toml file"""
    # 'feature' is used to import the environment.devenv.yml contents as a feature.
    print(f"Coming soon ({file} {feature})")
