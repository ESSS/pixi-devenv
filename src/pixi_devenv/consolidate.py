from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from pixi_devenv.project import Project, Spec, ProjectName, EnvVarValue, DevEnvError
from pixi_devenv.workspace import Workspace


def consolidate_devenv(workspace: Workspace) -> ConsolidatedProject:
    dependencies, pypi_dependencies = _consolidate_dependencies(workspace)
    return ConsolidatedProject(
        name=workspace.starting_project.name,
        dependencies=dependencies,
        pypi_dependencies=pypi_dependencies,
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
class MergedEnvVarValue:
    sources: Sources
    var: EnvVarValue


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
