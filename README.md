# pixi-devenv


## Why?

pixi-devenv is tool to work with multiple pixi projects in development mode.

pixi currently does not have full support to work with multiple projects in development mode. Development mode allows one to use have each project declaring its own dependencies, and work with all of them with live code so changes are reflected immediately, without the needing of creating/installing the projects as packages in the environment.

pixi-devenv makes it easy to aggregate multiple "projects" to create a single "product".

## Introduction

Here are a quick explanation of some `pixi` concepts that are important to understand to use `pixi-devenv`.

### `[dependencies]`

Lists the `conda` dependencies of a project. `[pypi-dependencies]` lists PyPI dependencies. `pixi` fully supports using PyPI packages, meaning PyPI packages are solved together with the conda packages.


```toml
[dependencies]
alive-progress = ">=3.2"
artifacts_cache = ">=3.0"
```

### `[activation]`

Defines which variables and scripts should be activated for the environment.

```toml
[activation]
scripts = [    
    ".pixi-activation/env-vars.sh",
]
CONDA_PY="310"
PATH = "$PIXI_PROJECT_ROOT/bin:$PATH"
```

### `[target.{NAME}]`


A `[target.{NAME}]` section can be used to specify platform specific configuration, such as `[target.win]` or `[target.linux]`. Generic terms are valid (`win`, `unix`), down to more specific ones (`linux-64`, `windows-64`).

Each `[target.{NAME}]` section contains its own `[dependencies]` and `[activation]` sections.

```toml
[target.win.dependencies]
pywin32 = ">=305"

[target.unix.dependencies]
sqlite = ">=3.40"

[target.linux-64.activation]
env = { JOBS = "6" }
```


### `[feature.NAME]`

Think of a `feature` as a group of `dependencies` and `activation` sections. They can be used to have a different set of dependencies for different purposes, like testing or linting tools, as well as different dependency matrixes. They are *additive* to the default `[environment]` and `[activation]` sections:

```toml
[feature.python310]
dependencies = { python = "3.10.*" }
activation = { env = { CONDA_PY = "310" } }

[feature.compile.target.win.dependencies]
dependency-walker = "*"
``` 

### `[environments]`

Environments are sets of one or more features. An environment will contain all the `dependencies` and `activation` of the features that compose the environment.

```toml
[environment]
py310 = ["python310", "compile"]
py312 = ["python312", "compile"]
```

## pixi-devenv

`pixi-devenv` configuration resides in a `pixi.devenv.toml` file. To update `pixi.toml` in case `pixi.devenv.toml` changes, execute:

```console
pixi run pixi-devenv
```

If your project includes `pixi-devenv` in its `dependencies`, but it can be run from a one-off environment:

```console
pixi exec pixi-devenv
```

Consider this project structure:

```
workspace/
    core/
        src/
        pixi.devenv.toml
    calc/
        src/
        pixi.devenv.toml
    web/
        src/
        pixi.devenv.toml
```

**Characteristics**

* `web` depends on `calc`, which depends on `core`.
* We have two features defined in `core`:
    * `test`: adds test specific dependencies.
    * `py310`: Python 3.10.
    * `py312`: Python 3.12.

### `core/pixi.devenv.toml`

The `pixi-devenv` configuration resides in the `devenv` table. This avoids confusion when looking at both `pixi.devenv.toml` file and `pixi.toml`, making the distintion clear.

```toml
[devenv]
# Mandatory: name of this project
# Question: should this actually be forbidden and forced to be the name of the directory?
name = "core"
channels = [
    "prefix.dev",
    "https://packages.company.com"
]
platforms = ["win-64", "linux-64"]
```

Basic information about the project. `channels` and `platforms` are inherited by downstream projects by default, but can also be overwritten.


```toml
[devenv.dependencies]
attrs = "*"
boltons = "*"

[devenv.target.win.dependencies]
pywin32 = "*"
```

Default dependencies, identical to pixi's `[dependencies]` section. They are inherited by default by downstream projects.


```toml
[devenv.constraints]
qt = ">=5.15"

[devenv.target.win.constraints]
vc = ">=14"
```

Default `constraints`. They are inherited by default by downstream projects.

`constraints` contain version specs similar to `[dependencies]`, but contrary to `dependencies` the specs are not part of the environment by default.

They will be added to the versions specifiers of the section *if* a downstream project explicitly declares that dependency.


```toml
[devenv.env-vars]
# Lists are prepended to existing variable of same name, with the appropriate joiner for the platform (':' on Linux, ';' on Windows).
# $project_dir is replaced by the project directory.
PYTHONPATH = ['$project_dir/src']

# Alternatives where it is possible to control if prepend or append.
# PYTHONPATH.append = ['{{ project_dir }}/src']
# PYTHONPATH.prepend = ['{{ project_dir }}/src']

# Strings are set directly.
JOBS = "6"

# Overwrite by platform uses the same syntax as usual.
[devenv.target.unix.env-vars]
CC = 'CC $CC'
```

Environment variables (note this is different from *environments*). By default they are inherited.

This takes the place of the `[activation]` section of the default pixi configuration.


```toml
[devenv.feature.python310]
dependencies = { python = "3.10.*" }
env-vars = { CONDA_PY = "310" }

[devenv.feature.python312]
dependencies = { python = "3.12.*" }
env-vars = { CONDA_PY = "312" }

[devenv.feature.test]
dependencies = { pytest = "*" }

[devenv.feature.compile]
dependencies = { cmake = "*" }
``` 

Feature configuration, identical to pixi's `[feature]` section. Features **are not** inherited automatically. The reason for that is that features that are not used by environments generate a warning, which would cause false warnings in downstream projects only because they decide to not use a feature available on upstream projects.


```toml
[devenv.environment]
py310 = ["python310"]
py310-test = ["python310", "test", "compile"]
py312 = ["python312"]
py312-test = ["python312", "test", "compile"]
```

Environment configuration, identical to pixi's `[environment]` section. Same as features, environments **are not inherited** by default.


### `calc/pixi.devenv.toml`


```toml
[devenv]
name = "calc"
# platforms = ["linux-64"]  # can overwrite platforms defined upstream.
# channels = ["conda-forge"]  # can overwrite platforms defined upstream.


# Mandatory: List of upstream projects. This should be a list pointing to the directory, relative to this directory, of the upstream's project `pixi.devenv.toml` file.
upstream = [
    "../core",
]

[devenv.dependencies]



[devenv.inherit]  # Optional
# Both settings can be a list instead of a bool, meaning to inherit dependencies only from the projects explicitly listed.
# dependencies = ["core"]
# Default to true, meaning default dependencies from all upstream projects are inherited. Using false means no dependencies are inherited.
dependencies = true
pypi-dependencies = true
env-vars = true

# Controls which features will be inherited. By default this table is empty, meaning no features are inherited.
[devenv.inherit.features]  # Optional
py310 = true  # inherits all features defined upstream named 'py310'.
# py310-test = ['core']  # instead of inheriting all features of the same name, you can inherit the feature only from specific upstream projects.
```

Note: `environments` **are never inherited**. 



## Differences to `conda-devenv`

[conda-devenv](https://github.com/ESSS/pixi-devenv) is a tool developed by ESSS with the same purpose as `pixi-devenv`: working with multiple projects in development mode. 

There is one important difference on how the tools work:

`conda-devenv`, on one hand, is a frontend tool. Developers work with it directly on their day to day work, even if they are not changing dependencies or adding/removing projects -- developers call `conda devenv` to create their environments. One consequence of this is that developers need to have `conda-devenv` installed in their root `conda` installation, which requires everyone to be using the exact same version `conda` version, because unfortunately bugs in conda happen (as in any software). The lack of native locking in `conda` requires using `conda-lock`, which by itself must also be of a compatible version with `conda` and `conda-devenv`, further complicating bootstrapping requirements.


`pixi-devenv`, on the other hand, is a code generation tool. You don't need to use it on your day to day work, because you deal with a plain `pixi.toml` file, using `pixi` directly. You only need `pixi-devenv` when you make changes to the dependencies of the project, or add/remove upstream projects -- in that case, you invoke `pixi-devenv` to update your `pixi.toml` file. This allows `pixi-devenv` to be implemented like any other tool, resolving the bootstrapping problem.



