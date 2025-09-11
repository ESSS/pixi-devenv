import graphlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self, Mapping, Iterator

from pixi_devenv.project import ProjectName, Project, DevEnvError


@dataclass
class Workspace:
    starting_project: Project

    projects: Mapping[ProjectName, Project]

    # Project -> their direct Upstream projects.
    graph: Mapping[ProjectName, Sequence[ProjectName]]

    _upstream_to_downstream_order: Sequence[ProjectName]

    @classmethod
    def from_starting_file(cls, path: Path) -> Self:
        starting_project = Project.from_file(path)
        to_process = [starting_project]
        projects = dict[ProjectName, Project]()
        graph = dict[ProjectName, list[ProjectName]]()
        while to_process:
            project = to_process.pop()
            if project.name in projects:
                continue
            projects[project.name] = project
            graph[project.name] = []

            for upstream in project.iter_upstream():
                upstream_project = Project.from_file(
                    project.directory.joinpath(upstream.path, "pixi.devenv.toml")
                )
                to_process.append(upstream_project)
                graph[project.name].append(upstream_project.name)

        sorter = graphlib.TopologicalSorter(graph)
        try:
            upstream_to_downstream_order = list(sorter.static_order())
        except graphlib.CycleError as e:
            raise DevEnvError(f"DevEnv dependencies are in a cycle: {e.args[1]}")
        return cls(starting_project, projects, graph, upstream_to_downstream_order)

    def iter_downstream(self) -> Iterator[Project]:
        yield from (self.projects[p] for p in self._upstream_to_downstream_order)

    def iter_upstream(self) -> Iterator[Project]:
        yield from (self.projects[p] for p in reversed(self._upstream_to_downstream_order))
