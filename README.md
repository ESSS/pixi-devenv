# pixi-devenv

pixi-devenv is tool to work with multiple pixi projects in development mode.

**WORK IN PROGRESS**

## `pixi.devenv.toml`

Environment configuration is placed in `pixi.devenv.toml` files, next to their usual `pixi.toml` files.

A `pixi.devenv.toml` file *includes* declarations from other projects by using the `includes` property:

```toml
includes = [
    "../core",
    "../calc",
]
```

Projects are included using paths to their directories, relative to the current file, as opposed to referencing a `.devenv` file (like `conda-devenv`). 

The reason is that `pixi-devenv` only supports a single `pixi.devenv.toml` file per project. Multiple environment and build variantes are contained all in the `pixi.devenv.toml` file, so there is no need for multiple `devenv` files.

To enable future extensions, this syntax is also valid:

```toml
includes = [
    "../core",
    { path="../calc" },
]
```



