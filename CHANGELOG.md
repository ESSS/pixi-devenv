# CHANGELOG

## UNRELEASED

*UNRELEASED*

* Added `--version` CLI option to display current version.
* Added support for `exclude-newer` in `pixi.devenv.toml`: the option propagates to downstream projects, with the most-downstream value winning.
* Now `[devenv.constraints]` are now passed through unchanged to `[constraints]` in the generated `pixi.toml`. 
  Since pixi `0.66` natively supports the `[constraints]` concept, constraints are now passed through unchanged and written to `[constraints]` independently of whether the same package appears in `[dependencies]` or `[pypi-dependencies]`.

## 0.3.1

*2026-02-09*

* [#5](https://github.com/ESSS/pixi-devenv/issues/5): Skip platform-specific environment variables if unsupported by downstream.

## 0.3.0

*2026-02-06*

* [#5](https://github.com/ESSS/pixi-devenv/issues/5): Skip platform-specific configuration if unsupported by downstream.

## 0.2.0

*2025-11-19*

* New `init` command used to generate initial `pixi.devenv.toml` and `pixi.toml` files.

## 0.1.0

*2025-11-06*

* First release.
