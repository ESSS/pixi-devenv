from textwrap import dedent

from pytest_regressions.file_regression import FileRegressionFixture

from pixi_devenv.update import update_pixi_config
from tests.devenv_tester import DevEnvTester


def test_basic_update(devenv_tester: DevEnvTester, file_regression: FileRegressionFixture) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv]
        channels = ["channel1", "channel2"]
        platforms = ["linux-64"]
        
        [devenv.env-vars]
        PYTHONPATH = ["${{ devenv_project_dir }}/src"]
        LD_LIBRARY_PATH = ["$CONDA_PREFIX/lib"]
        MYUSER = "$USER"
        MODE = "source"
        
        [devenv.dependencies]
        boltons = "24.0"

        [devenv.pypi-dependencies]
        attrs = "25.0"
        
        [devenv.target.unix]
        dependencies = { flock = "*" }
        env-vars = { FLOCK_MODE = "std", MYPYPATH = ["${{ devenv_project_dir }}/typing"] }
        
        [devenv.constraints]
        pyqt = ">=5.15"

        [devenv.feature.py310]
        dependencies = { python = "3.10.*", typing_extensions = "*" }
        env-vars = { CONDA_PY = "310" }
        
        [devenv.feature.py312]
        dependencies = { python = "3.12.*" }
        env-vars = { CONDA_PY = "312" }
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        
        [devenv.env-vars]
        PYTHONPATH = ["${{ devenv_project_dir }}/src"]
        MODE = "package"

        [devenv.dependencies]
        boltons = ">=24.2"      
        pyqt = { version="*", channel="conda-forge" }      
        """,
    )

    devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]
        
        [devenv.env-vars]
        PYTHONPATH = ["${{ devenv_project_dir }}/src"]

        [devenv.dependencies]
        numpy = ">=2.0"
        
        [devenv.feature.py310.dependencies]
        
        [devenv.feature.py312.dependencies]      
        """,
    )

    pixi = devenv_tester.write_pixi(
        "b",
        dedent("""
        [workspace]
        name = "some project"
        channels = ["conda-forge"]
                
        [environments]
        default = ["py310"]
        
        [dependencies]  # This will be overwritten
        foo = "*"
        """),
    )

    update_pixi_config(pixi.parent)
    file_regression.check(pixi.read_text(encoding="UTF-8"))


def test_exclude_newer_overrides_update(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture
) -> None:
    """Test that per-package exclude-newer overrides are written to the root [exclude-newer] and
    [pypi-exclude-newer] tables of pixi.toml."""
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv]
        channels = ["conda-forge"]
        platforms = ["linux-64"]
        exclude-newer = "2025-01-01"

        [devenv.exclude-newer-overrides]
        deps = "0d"

        [devenv.pypi-exclude-newer-overrides]
        some-internal-package = "0d"
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )

    pixi = devenv_tester.write_pixi(
        "a",
        dedent("""
        [workspace]
        name = "some project"
        channels = ["conda-forge"]
        platforms = ["linux-64"]
        """),
    )

    update_pixi_config(pixi.parent)
    file_regression.check(pixi.read_text(encoding="UTF-8"))


def test_exclude_newer_update(devenv_tester: DevEnvTester, file_regression: FileRegressionFixture) -> None:
    """Test that exclude-newer is written to the workspace section of pixi.toml."""
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv]
        channels = ["conda-forge"]
        platforms = ["linux-64"]
        exclude-newer = "7d"

        [devenv.dependencies]
        boltons = "24.0"
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )

    pixi = devenv_tester.write_pixi(
        "a",
        dedent("""
        [workspace]
        name = "some project"
        channels = ["conda-forge"]
        platforms = ["linux-64"]
        """),
    )

    update_pixi_config(pixi.parent)
    file_regression.check(pixi.read_text(encoding="UTF-8"))


def test_exclude_newer_overrides_removed_on_update(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture
) -> None:
    """Test that a stale `exclude-newer` field and `[exclude-newer]`/`[pypi-exclude-newer]` tables
    are removed from `pixi.toml` once they are no longer set in `pixi.devenv.toml`."""
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv]
        channels = ["conda-forge"]
        platforms = ["linux-64"]
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )

    pixi = devenv_tester.write_pixi(
        "a",
        dedent("""
        [workspace]
        name = "some project"
        channels = ["conda-forge"]
        platforms = ["linux-64"]
        exclude-newer = "2025-01-01" # Managed by devenv

        [exclude-newer] # Managed by devenv
        deps = "0d" # From: bootstrap

        [pypi-exclude-newer] # Managed by devenv
        some-internal-package = "0d" # From: bootstrap
        """),
    )

    update_pixi_config(pixi.parent)
    file_regression.check(pixi.read_text(encoding="UTF-8"))
