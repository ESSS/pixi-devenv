from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import PurePath, Path
from typing import assert_never, Sequence

from pixi_devenv.project import Project, Spec, ProjectName, EnvVarValue, DevEnvError, Aspect
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
    root_aspect = _consolidate_aspects(
        workspace, [(p, p.get_root_aspect()) for p in workspace.iter_downstream()]
    )

    all_targets = defaultdict[str, list[Project]](list)
    for project in workspace.iter_downstream():
        for target_name in project.target:
            all_targets[target_name].append(project)

    consolidated_target = dict[str, ConsolidatedAspect]()
    for target_name, projects in all_targets.items():
        aspect = _consolidate_aspects(workspace, [(p, p.target[target_name]) for p in projects])
        consolidated_target[target_name] = aspect

    return ConsolidatedProject(
        name=workspace.starting_project.name,
        dependencies=root_aspect.dependencies,
        pypi_dependencies=root_aspect.pypi_dependencies,
        env_vars=root_aspect.env_vars,
        target=consolidated_target,
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
    dependencies: dict[str, MergedSpec]
    pypi_dependencies: dict[str, MergedSpec]
    env_vars: dict[str, MergedEnvVarValue]


class ConsolidatedFeature:
    dependencies: dict[str, MergedSpec]
    pypi_dependencies: dict[str, MergedSpec]
    env_vars: dict[str, MergedEnvVarValue]
    target: dict[str, ConsolidatedAspect]


def _consolidate_aspects(
    workspace: Workspace,
    aspects: Sequence[tuple[Project, Aspect]],
) -> ConsolidatedAspect:
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
    inherit = starting_project.inherit

    for project, aspect in aspects:
        inherit_this_constraints = inherit.use_dependencies(
            project.name, starting_project
        ) or inherit.use_pypi_dependencies(project.name, starting_project)
        if inherit_this_constraints:
            update_specs(
                project, constraints, ((n, Spec.normalized(s)) for (n, s) in aspect.constraints.items())
            )

    dependencies: dict[str, MergedSpec] = {}
    pypi_dependencies: dict[str, MergedSpec] = {}

    for project, aspect in aspects:
        if inherit.use_dependencies(project.name, starting_project):
            update_specs(
                project, dependencies, ((n, Spec.normalized(s)) for (n, s) in aspect.dependencies.items())
            )
        if inherit.use_pypi_dependencies(project.name, starting_project):
            update_specs(
                project,
                pypi_dependencies,
                ((n, Spec.normalized(s)) for (n, s) in aspect.pypi_dependencies.items()),
            )

    result_env_vars: dict[str, MergedEnvVarValue] = {}

    for project, aspect in aspects:
        if not inherit.use_env_vars(project.name, starting_project):
            continue

        for name, env_var in aspect.env_vars.items():
            evaluated_env_var = ResolvedEnvVar.resolve(project, workspace, env_var)
            merged = MergedEnvVarValue(sources=(project.name,), var=evaluated_env_var)
            try:
                evaluated = result_env_vars[name]
                result_env_vars[name] = evaluated.merge(merged)
            except KeyError:
                result_env_vars[name] = merged

    return ConsolidatedAspect(
        dependencies=dependencies, pypi_dependencies=pypi_dependencies, env_vars=result_env_vars
    )
