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
