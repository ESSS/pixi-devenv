import pprint
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DevEnvTester:
    projects_path: Path

    def write_devenv(self, parent_path: str, contents: str) -> Path:
        toml = self.projects_path.joinpath(f"{parent_path}/pixi.devenv.toml")
        toml.parent.mkdir(parents=True, exist_ok=True)
        toml.write_text(contents)
        return toml

    def write_pixi(self, parent_path: str, contents: str) -> Path:
        toml = self.projects_path.joinpath(f"{parent_path}/pixi.toml")
        toml.parent.mkdir(parents=True, exist_ok=True)
        toml.write_text(contents)
        return toml

    def pprint_for_regression(self, obj: object) -> str:
        contents = pprint.pformat(obj, sort_dicts=False)
        contents = contents.replace(str(self.projects_path.as_posix()), "<TMP_PATH>")
        contents = contents.replace("WindowsPath(", "Path(")
        contents = contents.replace("PosixPath(", "Path(")
        return contents
