from __future__ import annotations

import os
import string
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import PurePath, Path
from typing import assert_never, Sequence

from pixi_devenv.project import Project, Spec, ProjectName, EnvVarValue, DevEnvError, Aspect, Feature
from pixi_devenv.workspace import Workspace


class Shell(Enum):
    """Abstracts the syntax differences for multiple shell scripts."""

    Cmd = auto()
    Bash = auto()

    @classmethod
    def from_target_name(cls, target_name: str) -> Shell:
        """Creates an instance based on the target name used in pixi standards ('win-64', 'linux-64', etc.)."""
        if target_name.startswith("win"):
            return Shell.Cmd
        else:
            return Shell.Bash

    def env_var(self, name: str) -> str:
        """Refer to an environment variable."""
        match self:
            case Shell.Cmd:
                return f"%{name}%"
            case Shell.Bash:
                return f"${{{name}}}"
            case unreachable:
                assert_never(unreachable)

    def define_keyword(self) -> str:
        """Keyword to define an environment variable."""
        match self:
            case Shell.Cmd:
                return "set"
            case Shell.Bash:
                return "export"
            case unreachable:
                assert_never(unreachable)

    def path_separator(self) -> str:
        """Character used to separate environment variables."""
        match self:
            case Shell.Cmd:
                return ";"
            case Shell.Bash:
                return ":"
            case unreachable:
                assert_never(unreachable)


def consolidate_devenv(workspace: Workspace) -> ConsolidatedProject:
    """
    Consolidates the given workspace definition, coalescing all pixi-devenv settings from the different files
    in the workspace into a single pixi definition.
    """
    root_aspect = _consolidate_aspects(
        workspace, [(p, p.get_root_aspect()) for p in workspace.iter_downstream()]
    )

    consolidated_target = _consolidate_target(workspace, list(workspace.iter_downstream()))
    consolidated_feature = _consolidate_feature(workspace)

    channels: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()

    for project in workspace.iter_downstream():
        if project.channels:
            channels = project.channels
        if project.platforms:
            platforms = project.platforms

    return ConsolidatedProject(
        name=workspace.starting_project.name,
        channels=channels,
        platforms=platforms,
        dependencies=root_aspect.dependencies,
        pypi_dependencies=root_aspect.pypi_dependencies,
        env_vars=root_aspect.env_vars,
        target=consolidated_target,
        feature=consolidated_feature,
    )


@dataclass
class ConsolidatedProject:
    """
    Result of consolidating all the projects in a `Workspace` in a single, final pixi.toml configuration.

    This class acts as the schema that will be written as a `pixi.toml` file.
    """

    name: str

    channels: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()

    dependencies: dict[str, MergedSpec] = field(default_factory=dict)
    pypi_dependencies: dict[str, MergedSpec] = field(default_factory=dict)
    env_vars: dict[str, MergedEnvVarValue] = field(default_factory=dict)
    target: dict[str, ConsolidatedAspect] = field(default_factory=dict)
    feature: dict[str, ConsolidatedFeature] = field(default_factory=dict)


type Sources = tuple[ProjectName, ...]


@dataclass(frozen=True)
class MergedSpec:
    """
    Specs from different projects merged together.

    For example, we might have project "a" with:

        pytest = ">=7.2"

    And downstream, project "b" with:

        pytest = { version = ">=8.0", channel = "conda-forge" }

    This will result in a merged spec of:

        pytest = { version = ">=7.2,>=8.0", build="", channel="conda-forge" }

    which will be written in the final `pixi.toml`file.

    Note:

    * Versions are merged together.
    * Build and channels cannot be merged, so the downstream-most project wins.
    """

    # Track which projects contributed to the spec.
    sources: Sources

    # Final merged spec.
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
    """
    An environment variable where the pixi-devenv placeholders have been resolved.

    Placeholders are strings in str-format that can appear in environment variables in pixi-devenv files
    that will be replaced by a different value when evaluated for the final pixi.toml file.

    Current placeholders are:

    * `devenv_project_dir` will be replaced by the directory of the current `pixi.devenv.toml` file.
    """

    value: EnvVarValue

    @classmethod
    def resolve(cls, project: Project, ws: Workspace, value: EnvVarValue) -> ResolvedEnvVar:
        relative = project.directory.relative_to(ws.starting_project.directory)
        normalized = Path(os.path.normpath(relative))
        mapping = {
            "devenv_project_dir": PurePath("${PIXI_PROJECT_ROOT}", normalized).as_posix(),
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
    """
    Environment variables from different projects merged together.

    For variables that are a single string, the downstream project wins.

    For variables that are a list, the items are joined together using the correct path separator, with
    downstream items appearing first.
    """

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

    def get_generic_value(self) -> str | None:
        match self.var.value:
            case str(v):
                t = string.Template(v)
                # Without any identifiers: does not require platform-specific replacements, so it is generic.
                if not t.get_identifiers():
                    return v
                else:
                    # Requires platform-specific replacement of the variables:
                    # "$FOO/lib" -> "${FOO}/lib" or "%FOO%/lib"
                    return None
            case tuple():
                # Lists always require platform-specific versions, to join them using the appropraite
                # path separator (':' or ';').
                return None
            case unreachable:
                assert_never(unreachable)


@dataclass
class ConsolidatedAspect:
    """
    Result of consolidating many aspects into a single aspect, merging the configurations.
    """

    dependencies: dict[str, MergedSpec]
    pypi_dependencies: dict[str, MergedSpec]
    env_vars: dict[str, MergedEnvVarValue]


@dataclass
class ConsolidatedFeature:
    """
    Result of consolidating many features into a single feature, merging the configurations.
    """

    dependencies: dict[str, MergedSpec]
    pypi_dependencies: dict[str, MergedSpec]
    env_vars: dict[str, MergedEnvVarValue]
    target: dict[str, ConsolidatedAspect]

    def is_empty(self) -> bool:
        return not self.dependencies and not self.pypi_dependencies and not self.env_vars and not self.target


@dataclass(frozen=True)
class FeatureWithProject:
    """Utility that tracks a project together with a feature."""

    project: Project
    feature: Feature

    @property
    def target(self) -> dict[str, Aspect]:
        return self.feature.target


def get_project_name(p: Project | FeatureWithProject) -> ProjectName:
    match p:
        case Project():
            return p.name
        case FeatureWithProject(project=project):
            return project.name
        case unreachable:
            assert_never(unreachable)


def _consolidate_aspects(
    workspace: Workspace,
    aspects: Sequence[tuple[Project | FeatureWithProject, Aspect]],
) -> ConsolidatedAspect:
    def update_specs(
        project_name: ProjectName,
        dependencies_dict: dict[str, MergedSpec],
        specs: Iterator[tuple[str, Spec]],
    ) -> None:
        for name, spec in specs:
            try:
                merged_spec = dependencies_dict[name]
                dependencies_dict[name] = merged_spec.add(name, project_name, spec)
            except KeyError:
                merged_spec = MergedSpec((project_name,), spec)
                if constraint := constraints.get(name):
                    merged_spec = merged_spec.add(name, constraint.sources, constraint.spec)
                dependencies_dict[name] = merged_spec

    constraints: dict[str, MergedSpec] = {}

    starting_project = workspace.starting_project
    inherit = starting_project.inherit

    for project_or_feature, aspect in aspects:
        project_name = get_project_name(project_or_feature)
        inherit_this_constraints = inherit.use_dependencies(
            project_name, starting_project
        ) or inherit.use_pypi_dependencies(project_name, starting_project)
        if inherit_this_constraints:
            update_specs(
                project_name, constraints, ((n, Spec.normalized(s)) for (n, s) in aspect.constraints.items())
            )

    dependencies: dict[str, MergedSpec] = {}
    pypi_dependencies: dict[str, MergedSpec] = {}

    for project_or_feature, aspect in aspects:
        project_name = get_project_name(project_or_feature)
        if inherit.use_dependencies(project_name, starting_project):
            update_specs(
                project_name,
                dependencies,
                ((n, Spec.normalized(s)) for (n, s) in aspect.dependencies.items()),
            )
        if inherit.use_pypi_dependencies(project_name, starting_project):
            update_specs(
                project_name,
                pypi_dependencies,
                ((n, Spec.normalized(s)) for (n, s) in aspect.pypi_dependencies.items()),
            )

    result_env_vars: dict[str, MergedEnvVarValue] = {}

    for project_or_feature, aspect in aspects:
        project_name = get_project_name(project_or_feature)
        if not inherit.use_env_vars(project_name, starting_project):
            continue

        match project_or_feature:
            case Project():
                project = project_or_feature
            case FeatureWithProject(project=p):
                project = p
            case unreachable:
                assert_never(unreachable)

        for name, env_var in aspect.env_vars.items():
            evaluated_env_var = ResolvedEnvVar.resolve(project, workspace, env_var)
            merged = MergedEnvVarValue(sources=(project_name,), var=evaluated_env_var)
            try:
                evaluated = result_env_vars[name]
                result_env_vars[name] = evaluated.merge(merged)
            except KeyError:
                result_env_vars[name] = merged

    return ConsolidatedAspect(
        dependencies=dependencies, pypi_dependencies=pypi_dependencies, env_vars=result_env_vars
    )


def _consolidate_target(
    workspace: Workspace, projects: Sequence[Project | FeatureWithProject]
) -> dict[str, ConsolidatedAspect]:
    all_targets = defaultdict[str, list[Project | FeatureWithProject]](list)
    for project in projects:
        for target_name in project.target:
            all_targets[target_name].append(project)

    consolidated_aspect = dict[str, ConsolidatedAspect]()
    for target_name, projects in all_targets.items():
        aspect = _consolidate_aspects(workspace, [(p, p.target[target_name]) for p in projects])
        consolidated_aspect[target_name] = aspect
    return consolidated_aspect


def _consolidate_feature(workspace: Workspace) -> dict[str, ConsolidatedFeature]:
    all_features = defaultdict[str, list[Project]](list)
    for project in workspace.iter_downstream():
        for feature_name in project.feature:
            all_features[feature_name].append(project)

    starting_project = workspace.starting_project
    inherit = starting_project.inherit

    result = dict[str, ConsolidatedFeature]()
    for feature_name, projects in all_features.items():
        aspects_and_projects = []
        features_with_projects = []

        for project in projects:
            if inherit.use_feature(feature_name, project.name, starting_project):
                aspects_and_projects.append((project, project.feature[feature_name].get_aspect()))
                features_with_projects.append(FeatureWithProject(project, project.feature[feature_name]))

        aspect = _consolidate_aspects(workspace, aspects_and_projects)
        target = _consolidate_target(workspace, features_with_projects)

        consolidated_feature = ConsolidatedFeature(
            dependencies=aspect.dependencies,
            pypi_dependencies=aspect.pypi_dependencies,
            env_vars=aspect.env_vars,
            target=target,
        )
        if not consolidated_feature.is_empty():
            result[feature_name] = consolidated_feature
    return result
