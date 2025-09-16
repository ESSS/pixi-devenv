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
class Root:
    devenv: Project


@dataclass
class Upstream:
    path: str

    @classmethod
    def normalized(cls, upstream: str | Upstream) -> Upstream:
        match upstream:
            case str() as path:
                return Upstream(path)
            case Upstream():
                return upstream
            case unreachable:
                assert_never(unreachable)


@dataclass
class Spec:
    version: str
    build: str = ""
    channel: str = ""

    @classmethod
    def normalized(cls, spec: Spec | str) -> Spec:
        match spec:
            case str() as version:
                return Spec(version=version, build="", channel="")
            case Spec():
                return spec
            case unreachable:
                assert_never(unreachable)


EnvVarValue = Union[str, tuple[str, ...]]


@serde.serde(tagging=serde.Untagged)
@dataclass
class Aspect:
    dependencies: dict[str, Spec | str] = serde.field(default_factory=dict)
    pypi_dependencies: dict[str, Spec | str] = serde.field(rename="pypi-dependencies", default_factory=dict)
    constraints: dict[str, Spec | str] = serde.field(default_factory=dict)
    env_vars: dict[str, EnvVarValue] = serde.field(rename="env-vars", default_factory=dict)


@serde.serde(tagging=serde.Untagged)
class Feature:
    dependencies: dict[str, Spec | str] = serde.field(default_factory=dict)
    pypi_dependencies: dict[str, Spec | str] = serde.field(rename="pypi-dependencies", default_factory=dict)
    constraints: dict[str, Spec | str] = serde.field(default_factory=dict)
    env_vars: dict[str, EnvVarValue] = serde.field(rename="env-vars", default_factory=dict)
    target: dict[str, Aspect] = serde.field(default_factory=dict)

    def get_aspect(self) -> Aspect:
        return Aspect(
            dependencies=self.dependencies,
            pypi_dependencies=self.pypi_dependencies,
            constraints=self.constraints,
            env_vars=self.env_vars,
        )


@serde.serde(tagging=serde.Untagged)
class Include:
    include: tuple[ProjectName, ...]


@serde.serde(tagging=serde.Untagged)
class Exclude:
    exclude: tuple[ProjectName, ...]


@serde.serde(tagging=serde.Untagged)
@dataclass
class Inheritance:
    dependencies: bool | Include | Exclude = True
    pypi_dependencies: bool | Include | Exclude = serde.field(rename="pypi-dependencies", default=True)
    env_vars: bool | Include | Exclude = serde.field(rename="env-vars", default=True)
    features: dict[str, bool | Include | Exclude] = serde.field(default_factory=dict)

    def use_dependencies(self, name: ProjectName, starting_project: Project) -> bool:
        return self._evaluate_for_project(self.dependencies, name, starting_project)

    def use_pypi_dependencies(self, name: ProjectName, starting_project: Project) -> bool:
        return self._evaluate_for_project(self.pypi_dependencies, name, starting_project)

    def use_env_vars(self, name: ProjectName, starting_project: Project) -> bool:
        return self._evaluate_for_project(self.env_vars, name, starting_project)

    def use_feature(self, feature_name: str, project_name: ProjectName, starting_project: Project) -> bool:
        if feature_name in starting_project.feature:
            return True
        if include_exclude := self.features.get(feature_name):
            return self._evaluate_for_project(include_exclude, project_name, starting_project)
        return False

    @staticmethod
    def _evaluate_for_project(
        include_exclude: bool | Include | Exclude, name: ProjectName, starting_project: Project
    ) -> bool:
        if name == starting_project.name:
            return True
        match include_exclude:
            case Include(include):
                return name in include
            case Exclude(exclude):
                return name not in exclude
            case bool() as include:
                return include
            case unreachable:
                assert_never(unreachable)


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
    dependencies: dict[str, Spec | str] = serde.field(default_factory=dict)
    pypi_dependencies: dict[str, Spec | str] = serde.field(rename="pypi-dependencies", default_factory=dict)
    constraints: dict[str, Spec | str] = serde.field(default_factory=dict)
    env_vars: dict[str, EnvVarValue] = serde.field(rename="env-vars", default_factory=dict)
    target: dict[str, Aspect] = serde.field(default_factory=dict)
    feature: dict[str, Feature] = serde.field(default_factory=dict)
    inherit: Inheritance = serde.field(default_factory=Inheritance)

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
        yield from (Upstream.normalized(x) for x in self.upstream)

    def get_root_aspect(self) -> Aspect:
        return Aspect(
            dependencies=self.dependencies,
            pypi_dependencies=self.pypi_dependencies,
            constraints=self.constraints,
            env_vars=self.env_vars,
        )
