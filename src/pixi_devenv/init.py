from pathlib import Path
from textwrap import dedent

from pixi_devenv.error import DevEnvError


def init_devenv(path: Path) -> None:
    """
    Initialize simple pixi.devenv.toml and pixi.toml files in the given directory.

    Raises DevEnvError if the files already exist, to prevent accidental overwrites.
    """
    devenv = path.joinpath("pixi.devenv.toml")
    pixi = path.joinpath("pixi.toml")
    if devenv.is_file():
        raise DevEnvError(f"{devenv.name} already exists, aborting.")
    if pixi.is_file():
        raise DevEnvError(f"{pixi.name} already exists, aborting.")

    source_dir = "source/python" if path.joinpath("source/python").is_dir() else "src"

    devenv.write_text(
        dedent(
            f"""\
            [devenv]
            channels = [
                "conda-forge",
            ]
            platforms = ["win-64", "linux-64"]
            
            [devenv.dependencies]
            
            [devenv.env-vars]
            PYTHONPATH = ["${{{{ devenv_project_dir }}}}/{source_dir}"]
            """,
        ),
    )

    pixi.write_text(
        dedent(
            """\
            [workspace]

            [environments]
            """,
        ),
    )
