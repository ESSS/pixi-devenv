# Releasing

We do not publish this package on PyPI, using the tool directly from the conda-forge package.

To make a new release:

1. Create a branch `release-X.Y.Z`.
1. Update the `version` field in `pyproject.toml`.
1. Update the `CHANGELOG.md`.
1. Run `uv lock` to update the pixi-devenv version in its lock file. 
1. Open a PR.
1. Once approved, create a [new GitHub release](https://github.com/ESSS/pixi-devenv/releases/new) using the `release-X.Y.Z` branch as source.
1. Merge it (**do not squash**).

Eventually the conda-forge bot will pick up the new release and open a PR in the [pixi-devenv feedstock](https://github.com/conda-forge/pixi-devenv-feedstock),
but you can kick-start the process by creating [a new issue](https://github.com/conda-forge/pixi-devenv-feedstock/issues/new/choose) (follow the instructions in the issue body). 
