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
        PYTHONPATH = ["{devenv_project_dir}/src"]
        LD_LIBRARY_PATH = ["$CONDA_PREFIX/lib"]
        MYUSER = "$USER"
        MODE = "source"
        
        [devenv.dependencies]
        boltons = "24.0"

        [devenv.pypi-dependencies]
        attrs = "25.0"
        
        [devenv.target.unix]
        dependencies = { flock = "*" }
        env-vars = { FLOCK_MODE = "std", MYPYPATH = ["{devenv_project_dir}/typing"] }
        
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
        PYTHONPATH = ["{devenv_project_dir}/src"]
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
        PYTHONPATH = ["{devenv_project_dir}/src"]

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
