import dataclasses
import string
from collections.abc import Mapping
from pathlib import Path
from typing import assert_never

import tomlkit.api
from tomlkit.items import Table


from pixi_devenv.consolidate import (
    consolidate_devenv,
    ConsolidatedProject,
    MergedSpec,
    MergedEnvVarValue,
    Shell,
    ConsolidatedFeature,
)
from pixi_devenv.project import DevEnvError
from pixi_devenv.workspace import Workspace


def update_pixi_config(root: Path) -> None:
    starting_file = root / "pixi.devenv.toml"
    target_file = root / "pixi.toml"

    if not starting_file.is_file():
        raise DevEnvError(f"{starting_file.name} not found in {root}.\nConsider running pixi-devenv init.")

    if not target_file.is_file():
        raise DevEnvError(f"{target_file.name} not found in {root}.\nConsider running pixi-devenv init.")

    consolidated = consolidate_devenv(Workspace.from_starting_file(starting_file))
    contents = target_file.read_text(encoding="UTF-8")
    new_contents = _update_pixi_contents(root, contents, consolidated)
    target_file.write_text(new_contents, encoding="UTF-8")


def _update_pixi_contents(root: Path, contents: str, consolidated: ConsolidatedProject) -> str:
    doc = tomlkit.parse(contents)

    _update_workspace_fields(doc, consolidated)
    tables = _get_project_or_feature_tables(consolidated)
    for name, table in tables.items():
        doc[name] = table

    features_table = _make_table()
    for feature_name, feature in consolidated.feature.items():
        tables = _get_project_or_feature_tables(feature)
        features_table[feature_name] = tables

    if features_table:
        doc["features"] = features_table

    new_contents = tomlkit.dumps(doc)
    return new_contents


_MANAGED_COMMENT = "Managed by devenv"


def _update_workspace_fields(doc: tomlkit.TOMLDocument, consolidated: ConsolidatedProject) -> None:
    doc["workspace"]["name"] = consolidated.name  # type:ignore[index]
    doc["workspace"]["name"].comment(_MANAGED_COMMENT)  # type:ignore[index, union-attr]

    doc["workspace"]["channels"] = consolidated.channels  # type:ignore[index]
    doc["workspace"]["channels"].comment(_MANAGED_COMMENT)  # type:ignore[index, union-attr]

    doc["workspace"]["platforms"] = consolidated.platforms  # type:ignore[index]
    doc["workspace"]["platforms"].comment(_MANAGED_COMMENT)  # type:ignore[index, union-attr]


def _get_project_or_feature_tables(
    consolidated: ConsolidatedProject | ConsolidatedFeature,
) -> dict[str, Table]:
    result: dict[str, Table] = {}
    if table := _create_dependencies_table(consolidated.dependencies):
        result["dependencies"] = table
    if table := _create_dependencies_table(consolidated.pypi_dependencies):
        result["pypi-dependencies"] = table

    grouped = _split_env_vars(consolidated.env_vars)

    if grouped.generic:
        env_table = _make_table()
        env_table.update(grouped.generic)

        activation_table = _make_table()
        activation_table["env"] = env_table
        result["activation"] = activation_table

    target_table = tomlkit.table()
    target_table.comment(_MANAGED_COMMENT)

    platform_specific_by_target = {}

    if grouped.platform_specific:
        platform_specific_by_target["unix"] = grouped.platform_specific
        platform_specific_by_target["windows"] = grouped.platform_specific

    if consolidated.target or grouped.platform_specific:
        for target_name, aspect in consolidated.target.items():
            current_target_table = _make_table()
            target_table[target_name] = current_target_table

            if table := _create_dependencies_table(aspect.dependencies):
                current_target_table["dependencies"] = table
            if table := _create_dependencies_table(aspect.pypi_dependencies):
                current_target_table["pypi-dependencies"] = table

            env_vars = dict(aspect.env_vars)
            if (existing_section := platform_specific_by_target.pop(target_name, None)) is not None:
                env_vars = dict(_merge_env_vars(env_vars, existing_section))

            if env_vars:
                env_table = _make_table()
                env_table["env"] = _render_env_vars(target_name, env_vars)
                current_target_table["activation"] = env_table

        for target_name, env_vars in platform_specific_by_target.items():
            current_target_table = _make_table()
            target_table[target_name] = current_target_table

            env_table = _make_table()
            env_table["env"] = _render_env_vars(target_name, env_vars)
            current_target_table["activation"] = env_table

    if target_table:
        result["target"] = target_table

    return result


def _make_table() -> Table:
    table = tomlkit.table()
    table.comment(_MANAGED_COMMENT)
    return table


@dataclasses.dataclass
class GroupedEnvironmentVariables:
    generic: dict[str, str]
    platform_specific: dict[str, MergedEnvVarValue]


def _merge_env_vars(
    b: Mapping[str, MergedEnvVarValue], a: Mapping[str, MergedEnvVarValue]
) -> Mapping[str, MergedEnvVarValue]:
    result = dict(b.items())

    for name in set(a).intersection(b):
        result[name] = a[name].merge(b[name])

    for name in a.keys() - b.keys():
        result[name] = a[name]
    return result


def _render_env_vars(target_name: str, env_vars: Mapping[str, MergedEnvVarValue]) -> Table:
    def substitute(value: str) -> str:
        template = string.Template(value)
        replacements = template.get_identifiers()
        mapping = {x: shell.env_var(x) for x in replacements}
        return template.safe_substitute(mapping)

    shell = Shell.from_target_name(target_name)
    rendered_vars: dict[str, str] = {}
    for name, env_var in sorted(env_vars.items()):
        match env_var.var.value:
            case str(value):
                rendered_vars[name] = substitute(value)
            case tuple(values):
                substituted_values = [substitute(x) for x in values] + [shell.env_var(name)]
                rendered_vars[name] = shell.path_separator().join(substituted_values)
            case unreachable:
                assert_never(unreachable)

    result = _make_table()
    result.update(rendered_vars)
    return result


def _split_env_vars(vars: Mapping[str, MergedEnvVarValue]) -> GroupedEnvironmentVariables:
    generic = {}
    platform_specific = {}
    for name, merged_env_var in vars.items():
        if (generic_value := merged_env_var.get_generic_value()) is not None:
            generic[name] = generic_value
        else:
            platform_specific[name] = merged_env_var
    return GroupedEnvironmentVariables(generic=generic, platform_specific=platform_specific)


def _create_dependencies_table(deps: Mapping[str, MergedSpec]) -> Table | None:
    result = tomlkit.table()
    result.comment(_MANAGED_COMMENT)

    for name, merged_spec in deps.items():
        if merged_spec.spec.is_version_only():
            result.add(name, merged_spec.spec.version)
        else:
            inline_table = tomlkit.inline_table()
            inline_table.comment(_MANAGED_COMMENT)
            inline_table.update(dataclasses.asdict(merged_spec.spec))
            result.add(name, inline_table)
        result[name].comment(f"From: {', '.join(merged_spec.sources)}")

    return result
