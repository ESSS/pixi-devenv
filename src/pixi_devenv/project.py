from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Any, NewType, assert_never

import serde.toml


class DevEnvError(Exception):
    pass


ProjectName = NewType("ProjectName", str)


@dataclass
class Upstream:
    path: str


@dataclass
class Spec:
    version: str
    build: str = ""
    channel: str = ""


EnvVarValue = Union[str, tuple[str, ...]]


@serde.serde(tagging=serde.Untagged)
@dataclass
class Aspect:
    dependencies: dict[str, Spec | str] | None = None
    pypi_dependencies: dict[str, Spec | str] | None = serde.field(
        rename="pypi-dependencies", default=None
    )
    constraints: dict[str, Spec | str] | None = None
    env_vars: dict[str, EnvVarValue] | None = serde.field(
        rename="env-vars", default=None
    )


@serde.serde(tagging=serde.Untagged)
class Feature:
    dependencies: dict[str, Spec | str] | None = None
    pypi_dependencies: dict[str, Spec | str] | None = serde.field(
        rename="pypi-dependencies", default=None
    )
    constraints: dict[str, Spec | str] | None = None
    env_vars: dict[str, EnvVarValue] | None = serde.field(
        rename="env-vars", default=None
    )
    target: dict[str, Aspect] | None = None


@serde.serde(tagging=serde.Untagged)
@dataclass
class Inheritance:
    dependencies: bool | tuple[str, ...] = True
    pypi_dependencies: bool | tuple[str, ...] = serde.field(
        rename="pypy-dependencies", default=True
    )
    env_vars: bool | tuple[str, ...] = serde.field(rename="env-vars", default=True)
    features: dict[str, bool | tuple[str, ...]] = serde.field(default_factory=dict)


@serde.serde(tagging=serde.Untagged)
@dataclass
class Project:
    # `name` exists only to raise an error if it is actually defined in the file: the name is defined
    # by the directory where the toml file resides.
    _name: str | None = serde.field(rename="name", default=None)
    # `environment` exists only to raise an error if it is actually defined in the file: environments are not manipulated
    # by pixi-devenv and should be defined directly in pixi.toml.
    environments: dict[str, Any] | None = None

    upstream: tuple[str | Upstream, ...] = ()
    dependencies: dict[str, Spec | str] | None = None
    pypi_dependencies: dict[str, Spec | str] | None = serde.field(
        rename="pypi-dependencies", default=None
    )
    constraints: dict[str, Spec | str] | None = None
    env_vars: dict[str, EnvVarValue] | None = serde.field(
        rename="env-vars", default=None
    )
    target: dict[str, Aspect] | None = None
    feature: dict[str, Feature] | None = None
    inherit: Inheritance | None = None

    filename: Path = serde.field(skip=True, init=False)

    @property
    def name(self) -> ProjectName:
        assert self._name is not None
        return ProjectName(self._name)

    @property
    def directory(self) -> Path:
        return self.filename.parent

    @classmethod
    def from_file(cls, path: Path) -> Project:
        root = serde.toml.from_toml(Root, path.read_text(encoding="UTF-8"))
        if root.devenv._name is not None:
            raise DevEnvError(
                f"In file {path}:\ndevenv.name should not be defined explicitly, it is derived from the directory name."
            )
        if root.devenv.environments is not None:
            raise DevEnvError(
                f"In file {path}:\ndevenv.environments table should not be defined in pixi.devenv.toml, define directly in pixi.toml."
            )
        root.devenv.filename = path.absolute()
        root.devenv._name = ProjectName(path.parent.name)
        return root.devenv

    def iter_upstream(self) -> Iterator[Upstream]:
        for upstream in self.upstream:
            match upstream:
                case str() as path:
                    yield Upstream(path)
                case Upstream():
                    yield upstream
                case unreachable:
                    assert_never(unreachable)


@dataclass
class Root:
    devenv: Project
