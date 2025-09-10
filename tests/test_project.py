import pytest
from pytest_regressions.file_regression import FileRegressionFixture

from pixi_devenv.project import Project, DevEnvError
from tests.devenv_tester import DevEnvTester


def test_parse_complete_case(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture
) -> None:
    contents = """
    [devenv]
    upstream = [
        "../core",
        { path = "../calc" }
    ]
    
    [devenv.inherit]
    dependencies = false
    pypi-dependencies = ["core"]
    env-vars = ["core"]
    
    [devenv.inherit.features]
    py310 = true
    py310-test = ["core"]
    
    [devenv.dependencies]
    boltons = "*"
    pytest = { version="*", build="a" }
    
    [devenv.pypy-dependencies]
    pytest-mock = "*"
    
    [devenv.constraints]
    qt = ">=5.15"
    
    [devenv.target.win.dependencies]
    pywin32 = ">=3.20"
    
    [devenv.target.win.constraints]
    vc = ">=14"
    
    [devenv.env-vars]
    PYTHONPATH = ['{{ project_dir }}/src']
    JOBS = "6"
    
    [devenv.feature.python310]
    dependencies = { python = "3.10.*" }
    constraints = { mypy = ">=1.15" }
    env-vars = { CONDA_PY = "310" }
    
    [devenv.feature.python312]
    dependencies = { python = "3.12.*" }
    constraints = { mypy = ">=1.16" }
    env-vars = { CONDA_PY = "312" }
    
    [devenv.feature.compile.target.win.dependencies]
    dependency-walker = "*"
    
    [devenv.feature.compile.target.win.constraints]
    cmake = ">=3.50"
    
    [devenv.feature.compile.target.unix.dependencies]
    rhash = { version = ">=1.4.3", channel="https://company.com/get/conda-forge" }    
    """

    toml = devenv_tester.write_devenv("gui", contents)

    project = Project.from_file(toml)
    assert project.filename == toml
    assert project.directory == toml.parent

    file_regression.check(devenv_tester.pprint_for_regression(project))


def test_environment_error(devenv_tester: DevEnvTester) -> None:
    contents = """    
    [devenv.environments]
    default = ["python310"]
    """
    toml = devenv_tester.write_devenv("gui", contents)
    with pytest.raises(DevEnvError):
        Project.from_file(toml)
