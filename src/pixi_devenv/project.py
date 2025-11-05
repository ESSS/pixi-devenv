from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Any, NewType, assert_never

import serde.toml


class DevEnvError(Exception):
    """Errors raised explicitly by pixi-devenv."""


ProjectName = NewType("ProjectName", str)


@dataclass
class Root:
    """Schema for the root definition in a pixi.devenv.toml file: [devenv]."""

    devenv: Project


@dataclass
class Upstream:
    """Schema for an entries in `[devenv.upstream]`.

    Supports either a direct string:

        [devenv]
        upstream = ["../core"]

    Or dict form:

        [devenv]
        upstream = [{path = "../core"}]

    The latter is more extensible in case we want to add more settings in the future.
    """

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
    """
    Schema for a package spec definition.

    Supports either a direct string:

        [devenv.dependencies]
        pytest = ">=7.2"

    Or dict form:

        [devenv.dependencies]
        pytest = { version = ">=7.2", build="ab", channel="packages.company/custom" }
    """

    version: str
    build: str = ""
    channel: str = ""

    @classmethod
    def normalized(cls, spec: Spec | str) -> Spec:
        match spec:
            case str() as version:
                return Spec(version=version)
            case Spec():
                return spec
            case unreachable:
                assert_never(unreachable)

    def is_version_only(self) -> bool:
        return not self.build and not self.channel


# Type for the value of an environment variable.
# It can be either:
# A single string, in which case the environment variable is set to that value.
# A tuple of strings, in which case the values are *appended* to the existing environment variable, using
# the proper separator for the platform.
EnvVarValue = Union[str, tuple[str, ...]]


@serde.serde(tagging=serde.Untagged)
@dataclass
class Aspect:
    """
    Holds a set of dependencies, constraints and environment variables.

    An aspect is used in the definition of a feature or the "default" section in a devenv file.
    """

    # Direct conda dependencies.
    dependencies: dict[str, Spec | str] = serde.field(default_factory=dict)

    # Direct PyPI dependencies.
    pypi_dependencies: dict[str, Spec | str] = serde.field(rename="pypi-dependencies", default_factory=dict)

    # Constraints.
    # Constraints define a version restriction on downstream packages that explicitly depend on the constraint, but
    # the constrained package is not directly added as a dependency.
    constraints: dict[str, Spec | str] = serde.field(default_factory=dict)

    # Environment variables.
    env_vars: dict[str, EnvVarValue] = serde.field(rename="env-vars", default_factory=dict)


@serde.serde(tagging=serde.Untagged)
class Feature:
    """
    Defines a feature in pixi.devenv.toml file.

    To follow pixi's schema for features, we replicate the attributes of an aspect, with the addition that
    we can specify more specific Aspects for target platforms.
    """

    # Same as `Aspect.dependencies`.
    dependencies: dict[str, Spec | str] = serde.field(default_factory=dict)

    # Same as `Aspect.pypi_dependencies`.
    pypi_dependencies: dict[str, Spec | str] = serde.field(rename="pypi-dependencies", default_factory=dict)

    # Same as `Aspect.constraints`.
    constraints: dict[str, Spec | str] = serde.field(default_factory=dict)

    # Same as `Aspect.env_vars`.
    env_vars: dict[str, EnvVarValue] = serde.field(rename="env-vars", default_factory=dict)

    # Target-specific aspects for this feature.
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
    """
    Schema for an item in an Inheritance section that should be included when consolidating.

        [devenv.inherit]
        env-vars.include = ["core"]
    """

    include: tuple[ProjectName, ...]


@serde.serde(tagging=serde.Untagged)
class Exclude:
    """
    Schema for an item in an Inheritance section that should be excluded when consolidating.

        [devenv.inherit]
        env-vars.exclude = ["core"]
    """

    exclude: tuple[ProjectName, ...]


@serde.serde(tagging=serde.Untagged)
@dataclass
class Inheritance:
    """
    Controls how we inherit different aspects from upstream projects.

    The simplest form is using a boolean, meaning to inherit the specified aspect (dependencies, pypi_dependencies, env-vars)
    from all our upstream projects:

        [devenv.inherit]
        dependencies = false

    Alternatively, you can use `.include` and `.exclude` prefixes to include/exclude specific projects only.

        [devenv.inherit]
        pypi-dependencies.exclude = ["core"]
        env-vars.include = ["core"]
    """

    dependencies: bool | Include | Exclude = True
    pypi_dependencies: bool | Include | Exclude = serde.field(rename="pypi-dependencies", default=True)
    env_vars: bool | Include | Exclude = serde.field(rename="env-vars", default=True)
    features: dict[str, bool | Include | Exclude] = serde.field(default_factory=dict)

    def use_dependencies(self, name: ProjectName, starting_project: Project) -> bool:
        """If we should inherit dependencies from the given project, considering the starting project."""
        return self._evaluate_for_project(self.dependencies, name, starting_project)

    def use_pypi_dependencies(self, name: ProjectName, starting_project: Project) -> bool:
        """If we should inherit pypi_dependencies from the given project, considering the starting project."""
        return self._evaluate_for_project(self.pypi_dependencies, name, starting_project)

    def use_env_vars(self, name: ProjectName, starting_project: Project) -> bool:
        """If we should inherit env-vars from the given project, considering the starting project."""
        return self._evaluate_for_project(self.env_vars, name, starting_project)

    def use_feature(self, feature_name: str, project_name: ProjectName, starting_project: Project) -> bool:
        """If we should inherit the feature from the given project, considering the starting project."""
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
    """
    Schema that defines a project for pixi-devenv, containing its upstream projects, direct dependencies, environment variables, etc.

    This schema is what we primarily see when looking at an environment devenv file.
    """

    # `name` exists only to raise an error if it is actually defined in the file: users should not
    # explicitly define a name, the name is implicitly defined by the name of the directory where the
    # toml file resides.
    _name: str | None = serde.field(rename="name", default=None)

    # `environment` exists only to raise an error if it is actually defined in the file: environments are not manipulated
    # by pixi-devenv and should be defined directly in pixi.toml.
    environments: dict[str, Any] | None = None

    # List of channels to use for conda packages, in order of priority.
    channels: tuple[str, ...] = ()

    # List of platforms that this project supports.
    platforms: tuple[str, ...] = ()

    # List of upstream projects.
    upstream: tuple[str | Upstream, ...] = ()

    # Same as `Aspect.dependencies`.
    dependencies: dict[str, Spec | str] = serde.field(default_factory=dict)

    # Same as `Aspect.pypi_dependencies`.
    pypi_dependencies: dict[str, Spec | str] = serde.field(rename="pypi-dependencies", default_factory=dict)

    # Same as `Aspect.constraints`.
    constraints: dict[str, Spec | str] = serde.field(default_factory=dict)

    # Same as `Aspect.env_vars`.
    env_vars: dict[str, EnvVarValue] = serde.field(rename="env-vars", default_factory=dict)

    # Target-specific aspects (dependencies, environment variables, etc.).
    target: dict[str, Aspect] = serde.field(default_factory=dict)

    # Project features.
    feature: dict[str, Feature] = serde.field(default_factory=dict)

    # Controls how we inherit aspects from upstream projects.
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
    def from_file(cls, devenv_file: Path) -> Project:
        root = serde.toml.from_toml(Root, devenv_file.read_text(encoding="UTF-8"))
        if root.devenv._name is not None:
            raise DevEnvError(
                f"In file {devenv_file}:\ndevenv.name should not be defined explicitly, it is derived from the directory name."
            )
        if root.devenv.environments is not None:
            raise DevEnvError(
                f"In file {devenv_file}:\ndevenv.environments table should not be defined in pixi.devenv.toml, define directly in pixi.toml."
            )
        root.devenv.filename = devenv_file.absolute()
        root.devenv._name = ProjectName(devenv_file.parent.name)
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
