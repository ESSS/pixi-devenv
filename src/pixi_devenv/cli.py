from pathlib import Path

from typer import Typer

app = Typer()


@app.command()
def update(path: Path | None = None) -> None:
    print(f"updating, {path}")


@app.command()
def hello(path: Path | None = None) -> None:
    print(f"updating, {path}")
