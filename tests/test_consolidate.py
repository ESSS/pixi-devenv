import pytest
from pytest_regressions.file_regression import FileRegressionFixture

from pixi_devenv.consolidate import consolidate_devenv, MergedSpec, target_matches_platforms
from pixi_devenv.project import ProjectName, Spec
from pixi_devenv.error import DevEnvError
from pixi_devenv.workspace import Workspace
from tests.devenv_tester import DevEnvTester


@pytest.mark.parametrize(
    "target_name,platforms,expected",
    [
        # Empty platforms matches all.
        ("win", (), True),
        # Exact match.
        ("linux-64", ("linux-64", "win-64"), True),
        ("linux-64", ("win-64",), False),
        # Windows selector.
        ("win", ("win-64",), True),
        ("windows", ("win-64",), True),
        ("win", ("linux-64",), False),
        # Linux selector.
        ("linux", ("linux-64",), True),
        ("linux", ("win-64",), False),
        # macOS selector.
        ("osx", ("osx-64",), True),
        ("macos", ("osx-arm64",), True),
        ("osx", ("linux-64",), False),
        # Unix selector (everything except Windows).
        ("unix", ("linux-64",), True),
        ("unix", ("osx-64",), True),
        ("unix", ("win-64",), False),
    ],
)
def test_target_matches_platforms(target_name: str, platforms: tuple[str, ...], expected: bool) -> None:
    assert target_matches_platforms(target_name, platforms) is expected


def test_merged_spec() -> None:
    # Collapse "*" versions -- "*,*" is valid but distracting, as is "*,>=1.0".
    m = MergedSpec((ProjectName("a"),), Spec("*"))
    assert m.add("lib", ProjectName("b"), Spec("*")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec("*")
    )
    assert m.add("lib", ProjectName("b"), Spec(">=1.0")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=1.0")
    )
    m = MergedSpec((ProjectName("a"),), Spec(">=1.0"))
    assert m.add("lib", ProjectName("b"), Spec("*")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=1.0")
    )

    # Add another versioned spec.
    m = MergedSpec((ProjectName("a"),), Spec(">=12.0"))
    assert m.add("lib", ProjectName("b"), Spec(">=13.2")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=12.0,>=13.2")
    )
    assert m.add("lib", ProjectName("b"), Spec(">=13.2", build="b1")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=12.0,>=13.2", build="b1")
    )
    assert m.add("lib", ProjectName("b"), Spec(">=13.2", channel="conda-forge")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")),
        Spec(">=12.0,>=13.2", channel="conda-forge"),
    )

    # Merge 'build'.
    m2 = MergedSpec((ProjectName("a"),), Spec(">=12.0", build="b1"))
    assert m2.add("lib", ProjectName("b"), Spec(">=13.2")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=12.0,>=13.2", build="b1")
    )
    assert m2.add("lib", ProjectName("b"), Spec(">=13.2", build="b1")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=12.0,>=13.2", build="b1")
    )
    with pytest.raises(DevEnvError, match="Conflicting builds"):
        _ = m2.add("lib", ProjectName("b"), Spec(">=13.2", build="b99"))

    # Merge 'channel'.
    m2 = MergedSpec((ProjectName("a"),), Spec(">=12.0", channel="ch1"))
    assert m2.add("lib", ProjectName("b"), Spec(">=13.2")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=12.0,>=13.2", channel="ch1")
    )
    assert m2.add("lib", ProjectName("b"), Spec(">=13.2", channel="ch1")) == MergedSpec(
        (ProjectName("a"), ProjectName("b")), Spec(">=12.0,>=13.2", channel="ch1")
    )
    with pytest.raises(DevEnvError, match="Conflicting channels"):
        _ = m2.add("lib", ProjectName("b"), Spec(">=13.2", channel="ch99"))


def test_dependencies(devenv_tester: DevEnvTester, file_regression: FileRegressionFixture) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv.dependencies]
        boltons = "24.0"
        
        [devenv.pypi-dependencies]
        attrs = "25.0"        
        """,
    )
    a_toml = devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        
        [devenv.dependencies]
        boltons = ">=24.2"      
        pyqt = "*"      
        """,
    )
    ws = Workspace.from_starting_file(a_toml)
    project = consolidate_devenv(ws)
    file_regression.check(devenv_tester.pprint_for_regression(project))


def test_dependencies_with_constraints(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture
) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv.constraints]
        pyqt = ">=5.15"
        boltons = "24.0"
        foobar = "1.0"  # Will not appear because no downstream projects directly depend on it.
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]

        [devenv.pypi-dependencies]
        boltons = ">=23.0"   
        attrs = "*"   
        """,
    )
    b_toml = devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]

        [devenv.dependencies]
        pyqt = "*"      
        """,
    )
    ws = Workspace.from_starting_file(b_toml)
    project = consolidate_devenv(ws)
    file_regression.check(devenv_tester.pprint_for_regression(project))


def test_dependencies_inheritance(
    devenv_tester: DevEnvTester,
    file_regression: FileRegressionFixture,
    request: pytest.FixtureRequest,
) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv.dependencies]
        boltons = ">=24.0"
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]

        [devenv.dependencies]
        boltons = ">=23.0"   
        pytest = "*"   
        
        [devenv.pypi-dependencies]
        fast-api = "*"
        """,
    )
    devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]

        [devenv.dependencies]
        coverage = "21.0"

        [devenv.pypi-dependencies]
        flask = "*"
        """,
    )

    c_toml = devenv_tester.write_devenv(
        "c",
        """
        devenv.upstream = ["../b"]

        [devenv.dependencies]
        pillow = "21.0"

        [devenv.pypi-dependencies]
        pytest-mock = "*"

        [devenv.inherit]
        dependencies = false
        pypi-dependencies = false
        """,
    )
    ws = Workspace.from_starting_file(c_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project),
        basename=f"{request.node.name}_no_inheritance",
    )

    c_toml = devenv_tester.write_devenv(
        "c",
        """
        devenv.upstream = ["../b"]

        [devenv.dependencies]
        pillow = "21.0"

        [devenv.pypi-dependencies]
        pytest-mock = "*"

        [devenv.inherit]
        dependencies = true
        pypi-dependencies.exclude = ["a"]
        """,
    )
    ws = Workspace.from_starting_file(c_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project),
        basename=f"{request.node.name}_bootstrap_inheritance",
    )


def test_env_vars(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture, request: pytest.FixtureRequest
) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv.env-vars]
        CONDA_PY = "310"
        DOCS = "${{ devenv_project_dir }}/bootstrap-docs"
        PYTHONPATH = ["${{ devenv_project_dir }}/src"]
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        [devenv.env-vars]
        PYTHONPATH = ["${{ devenv_project_dir }}/src", "${{ devenv_project_dir }}/artifacts-$CONDA_PY"]
        """,
    )
    b_toml = devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]

        [devenv.env-vars]
        PYTHONPATH = ["${{ devenv_project_dir }}/src"]
        DOCS = "${{ devenv_project_dir }}/b-docs"
        README = "${{ devenv_project_dir }}/README.md"
        """,
    )
    ws = Workspace.from_starting_file(b_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project),
        basename=f"{request.node.name}",
    )

    c_toml = devenv_tester.write_devenv(
        "c",
        """
        devenv.upstream = ["../b"]

        [devenv.env-vars]
        PYTHONPATH = ["${{ devenv_project_dir }}/src"]
        
        [devenv.inherit]
        env-vars.exclude = ["a", "b"]
        """,
    )
    ws = Workspace.from_starting_file(c_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project),
        basename=f"{request.node.name}_no_inheritance",
    )


def test_targets(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture, request: pytest.FixtureRequest
) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv.target.win]        
        dependencies = { pywin32 = "*" }
        env-vars = { PLATFORM = "windows", MYPYPATH = ["${{ devenv_project_dir }}/src"] }
        
        [devenv.target.linux-64]
        dependencies = { sysftcl = "*" }
        env-vars = { PLATFORM = "linux64" }  
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        
        [devenv.target.unix]
        pypi-dependencies = { file-lock = "*" }
        env-vars = { LOCK_MODE = "fs" } 
        """,
    )
    b_toml = devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]

        [devenv.target.win]
        env-vars = { MYPYPATH = ["${{ devenv_project_dir }}/src"] }

        [devenv.target.unix]
        pypi-dependencies = { pthread = "*" }
        env-vars = { PARALLEL_MODE = "threads" } 
        """,
    )
    ws = Workspace.from_starting_file(b_toml)
    project = consolidate_devenv(ws)
    file_regression.check(devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}")

    b_toml = devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]

        [devenv.target.win]
        env-vars = { MYPYPATH = ["${{ devenv_project_dir }}/src"] }

        [devenv.target.unix]
        pypi-dependencies = { pthread = "*" }
        env-vars = { PARALLEL_MODE = "threads" }
        
        [devenv.inherit]
        dependencies = false
        env-vars.include = ["bootstrap"] 
        """,
    )
    ws = Workspace.from_starting_file(b_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_inheritance"
    )


def test_features(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture, request: pytest.FixtureRequest
) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv.feature.py310]        
        dependencies = { python = "3.10.*" }
        env-vars = { CONDA_PY = "310" }
        
        [devenv.feature.py310.target.windows]        
        dependencies = { pywin32 = "*" }
        env-vars = { PLATFORM = "windows-py310" }
        
        [devenv.feature.py310.target.linux]        
        env-vars = { PLATFORM = "linux-py310" }
          
        [devenv.feature.py312]
        dependencies = { python = "3.12.*" }
        env-vars = { CONDA_PY = "312" }
        
        [devenv.feature.py312.target.windows]        
        dependencies = { pywin32 = "35.0" }
        env-vars = { PLATFORM = "windows-py312" }
        
        [devenv.feature.py312.target.linux]        
        env-vars = { PLATFORM = "linux-py312" }
        
        [devenv.feature.test]
        dependencies = { pytest = "*" }
        """,
    )
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]

        [devenv.feature.py310.target.windows]        
        dependencies = { pillow = "*" }
        env-vars = { MYPYPATH = ["${{ devenv_project_dir }}/src"] }
        """,
    )
    b_toml = devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]

        [devenv.inherit.features]
        py310.include = ["bootstrap"]
        py312 = true
        """,
    )
    ws = Workspace.from_starting_file(b_toml)
    project = consolidate_devenv(ws)
    file_regression.check(devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}")

    # Inherit py310 in b because we defined the feature too.
    b_toml = devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]        
        
        [devenv.feature.py310.target.windows]
        env-vars = { MYPYPATH = ["${{ devenv_project_dir }}/src"] } 
        """,
    )
    ws = Workspace.from_starting_file(b_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_inheritance"
    )

    # No feature inherited unless explicitly inherited or defining the feature.
    b_toml = devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../a"]        
        """,
    )
    ws = Workspace.from_starting_file(b_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_no_inheritance"
    )


def test_channels_and_platforms(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture, request: pytest.FixtureRequest
) -> None:
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv]
        channels = ["conda-forge"] 
        platforms = ["win-64", "linux-64"] 
        """,
    )
    a_toml = devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )
    ws = Workspace.from_starting_file(a_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_from_bootstrap"
    )

    a_toml = devenv_tester.write_devenv(
        "a",
        """
        [devenv]
        channels = ["company.com/channel1", "company.com/channel2"] 
        platforms = ["linux-64"]
        
        upstream = ["../bootstrap"]
        """,
    )
    ws = Workspace.from_starting_file(a_toml)
    project = consolidate_devenv(ws)
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_overwrite"
    )


def test_target_platform_filtering(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture, request: pytest.FixtureRequest
) -> None:
    """Test that targets are filtered based on downstream platform restrictions (ASIM-6522).."""
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv]
        platforms = ["linux-64", "win-64"]

        [devenv.target.win]
        dependencies = { pywin32 = "*" }

        [devenv.target.unix]
        dependencies = { libx11 = "*" }
    """,
    )

    # Downstream restricts to Linux only.
    a_toml = devenv_tester.write_devenv(
        "a",
        """
        [devenv]
        platforms = ["linux-64"]
        upstream = ["../bootstrap"]
    """,
    )
    ws = Workspace.from_starting_file(a_toml)
    project = consolidate_devenv(ws)

    # Should have "unix" target but NOT "win" target.
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_linux_only"
    )

    # Downstream restricts to Windows only.
    a_toml = devenv_tester.write_devenv(
        "a",
        """
        [devenv]
        platforms = ["win-64"]
        upstream = ["../bootstrap"]
    """,
    )
    ws = Workspace.from_starting_file(a_toml)
    project = consolidate_devenv(ws)

    # Should have "win" target but NOT "unix" target.
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_win_only"
    )


def test_feature_target_platform_filtering(
    devenv_tester: DevEnvTester, file_regression: FileRegressionFixture, request: pytest.FixtureRequest
) -> None:
    """Test that feature targets are also filtered based on downstream platform restrictions (ASIM-6522)."""
    devenv_tester.write_devenv(
        "bootstrap",
        """
        [devenv]
        platforms = ["linux-64", "win-64"]

        [devenv.feature.test]
        dependencies = { pytest = "*" }

        [devenv.feature.test.target.win]
        dependencies = { pywin32 = "*" }

        [devenv.feature.test.target.unix]
        dependencies = { libx11 = "*" }
    """,
    )

    # Downstream restricts to Linux only.
    a_toml = devenv_tester.write_devenv(
        "a",
        """
        [devenv]
        platforms = ["linux-64"]
        upstream = ["../bootstrap"]

        [devenv.feature.test]
        dependencies = { coverage = "*" }
    """,
    )
    ws = Workspace.from_starting_file(a_toml)
    project = consolidate_devenv(ws)

    # Feature should have "unix" target but NOT "win" target.
    file_regression.check(
        devenv_tester.pprint_for_regression(project), basename=f"{request.node.name}_linux_only"
    )
