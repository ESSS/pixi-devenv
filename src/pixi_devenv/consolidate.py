from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import PurePath, Path
from typing import assert_never

from pixi_devenv.project import Project, Spec, ProjectName, EnvVarValue, DevEnvError
from pixi_devenv.workspace import Workspace


class Shell(Enum):
    Cmd = auto()
    Bash = auto()

    def env_var(self, name: str) -> str:
        match self:
            case Shell.Cmd:
                return f"%{name}%"
            case Shell.Bash:
                return f"${{{name}}}"
            case unreachable:
                assert_never(unreachable)

    def define_keyword(self) -> str:
        match self:
            case Shell.Cmd:
                return "set"
            case Shell.Bash:
                return "export"
            case unreachable:
                assert_never(unreachable)

    def path_separator(self) -> str:
        match self:
            case Shell.Cmd:
                return ";"
            case Shell.Bash:
                return ":"
            case unreachable:
                assert_never(unreachable)


def consolidate_devenv(workspace: Workspace) -> ConsolidatedProject:
    dependencies, pypi_dependencies = _consolidate_dependencies(workspace)
    env_vars = _consolidate_env_vars(workspace)
    return ConsolidatedProject(
        name=workspace.starting_project.name,
        dependencies=dependencies,
        pypi_dependencies=pypi_dependencies,
        env_vars=env_vars,
    )


@dataclass
class ConsolidatedProject:
    name: str

    dependencies: dict[str, MergedSpec] = field(default_factory=dict)
    pypi_dependencies: dict[str, MergedSpec] = field(default_factory=dict)
    env_vars: dict[str, MergedEnvVarValue] = field(default_factory=dict)
    target: dict[str, ConsolidatedAspect] = field(default_factory=dict)
    feature: dict[str, ConsolidatedFeature] = field(default_factory=dict)


type Sources = tuple[ProjectName, ...]


@dataclass(frozen=True)
class MergedSpec:
    sources: Sources
    spec: Spec

    def add(self, spec_name: str, sources: ProjectName | tuple[ProjectName, ...], spec: Spec) -> MergedSpec:
        if self.spec.version != "*" and spec.version != "*":
            version = f"{self.spec.version},{spec.version}"
        elif self.spec.version != "*":
            version = self.spec.version
        else:
            version = spec.version

        if self.spec.build and spec.build and self.spec.build != spec.build:
            raise DevEnvError(
                f"Conflicting builds declared for {spec_name} in {self.sources} and {sources}: {self.spec.build}, {spec.build}"
            )
        build = self.spec.build or spec.build

        if not isinstance(sources, tuple):
            sources = (sources,)

        if self.spec.channel and spec.channel and self.spec.channel != spec.channel:
            raise DevEnvError(
                f"Conflicting channels declared for {spec_name} in {self.sources} and {sources}: {self.spec.channel}, {spec.channel}"
            )
        channel = self.spec.channel or spec.channel

        return MergedSpec(
            sources=self.sources + sources,
            spec=Spec(version=version, build=build, channel=channel),
        )


@dataclass(frozen=True)
class ResolvedEnvVar:
    value: EnvVarValue

    @classmethod
    def resolve(cls, project: Project, ws: Workspace, value: EnvVarValue) -> ResolvedEnvVar:
        relative = project.directory.relative_to(ws.starting_project.directory)
        normalized = Path(os.path.normpath(relative))
        mapping = {
            "devenv_project_dir": PurePath("${PIXI_PROJECT_DIR}", normalized).as_posix(),
        }

        def replace_devenv_vars(s: str) -> str:
            return s.format(**mapping)

        match value:
            case str() as single_value:
                return ResolvedEnvVar(replace_devenv_vars(single_value))
            case tuple() as values:
                return ResolvedEnvVar(tuple(replace_devenv_vars(x) for x in values))
            case unreachable:
                assert_never(unreachable)


@dataclass(frozen=True)
class MergedEnvVarValue:
    sources: Sources
    var: ResolvedEnvVar

    def merge(self, other: MergedEnvVarValue) -> MergedEnvVarValue:
        sources = self.sources + other.sources
        match other.var.value:
            case str():
                if not isinstance(self.var.value, str):
                    raise DevEnvError(
                        f"Incompatible env-var definition, they should have the same type: {other.var.value!r} vs {self.var.value!r}"
                    )
                return MergedEnvVarValue(sources=sources, var=other.var)
            case tuple():
                if not isinstance(self.var.value, tuple):
                    raise DevEnvError(
                        f"Incompatible env-var definition, they should have the same type: {other.var.value!r} vs {self.var.value!r}"
                    )
                new_values = ResolvedEnvVar(self.var.value + other.var.value)
                return MergedEnvVarValue(sources=sources, var=new_values)
            case unreachable:
                assert_never(unreachable)


@dataclass
class ConsolidatedAspect:
    dependencies: dict[str, MergedSpec] | None = None
    pypi_dependencies: dict[str, MergedSpec] | None = None
    env_vars: dict[str, MergedEnvVarValue] | None = None


class ConsolidatedFeature:
    dependencies: dict[str, MergedSpec] | None = None
    pypi_dependencies: dict[str, MergedSpec] | None = None
    env_vars: dict[str, MergedEnvVarValue] | None = None
    target: dict[str, ConsolidatedAspect] | None = None


def _consolidate_dependencies(
    workspace: Workspace,
) -> tuple[dict[str, MergedSpec], dict[str, MergedSpec]]:
    def update_specs(
        project: Project,
        dependencies_dict: dict[str, MergedSpec],
        specs: Iterator[tuple[str, Spec]],
    ) -> None:
        for name, spec in specs:
            try:
                merged_spec = dependencies_dict[name]
                dependencies_dict[name] = merged_spec.add(name, project.name, spec)
            except KeyError:
                merged_spec = MergedSpec((project.name,), spec)
                if constraint := constraints.get(name):
                    merged_spec = merged_spec.add(name, constraint.sources, constraint.spec)
                dependencies_dict[name] = merged_spec

    constraints: dict[str, MergedSpec] = {}

    starting_project = workspace.starting_project

    for project in workspace.iter_downstream():
        if starting_project.inherit.use_dependencies(
            project.name
        ) or starting_project.inherit.use_pypi_dependencies(project.name):
            update_specs(project, constraints, project.iter_constraints())

    dependencies: dict[str, MergedSpec] = {}
    pypi_dependencies: dict[str, MergedSpec] = {}

    for project in workspace.iter_downstream():
        if starting_project.inherit.use_dependencies(project.name) or project is starting_project:
            update_specs(project, dependencies, project.iter_dependencies())
        if starting_project.inherit.use_pypi_dependencies(project.name) or project is starting_project:
            update_specs(project, pypi_dependencies, project.iter_pypi_dependencies())

    return dependencies, pypi_dependencies


def _consolidate_env_vars(workspace: Workspace) -> dict[str, MergedEnvVarValue]:
    result: dict[str, MergedEnvVarValue] = {}

    starting_project = workspace.starting_project

    for project in workspace.iter_downstream():
        if not starting_project.inherit.use_env_vars(project.name):
            continue
        if project.inherit.use_env_vars(project.name):
            for name, env_var in project.env_vars.items():
                evaluated_env_var = ResolvedEnvVar.resolve(project, workspace, env_var)
                merged = MergedEnvVarValue(sources=(project.name,), var=evaluated_env_var)
                try:
                    evaluated = result[name]
                    result[name] = evaluated.merge(merged)
                except KeyError:
                    result[name] = merged

    return result
