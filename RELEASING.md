# Releasing

We do not publish this package on PyPI, using the tool directly from the conda-forge package.

To make a new release:

1. Create a branch `release-X.Y.Z`.
2. Update the `CHANGELOG.md` and open a PR.
3. Once approved, create a [new GitHub release](https://github.com/ESSS/pixi-devenv/releases/new) using the `release-X.Y.Z` branch as source.
4. Merge it (**do not squash**).

Eventually the conda-forge bot will pick up the new release and open a PR in the [pixi-devenv feedstock](https://github.com/conda-forge/sdl2-feedstock),
but you can kick-start the process by creating a new issue (follow the instructions in the issue body). 
