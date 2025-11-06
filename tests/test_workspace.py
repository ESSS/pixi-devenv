import pytest

from pixi_devenv.project import DevEnvError
from pixi_devenv.workspace import Workspace
from tests.devenv_tester import DevEnvTester


def test_standard(devenv_tester: DevEnvTester) -> None:
    devenv_tester.write_devenv("bootstrap", "[devenv]")
    devenv_tester.write_devenv(
        "pvt",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )
    devenv_tester.write_devenv(
        "xgui",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )
    devenv_tester.write_devenv(
        "alfasim/core",
        """
        devenv.upstream = ["../../pvt"]
        """,
    )
    devenv_tester.write_devenv(
        "alfasim/calc",
        """
        devenv.upstream = ["../core", "../../pvt"]
        """,
    )
    devenv_tester.write_devenv(
        "alfasim/gui",
        """
        devenv.upstream = ["../../xgui"]
        """,
    )

    app_toml = devenv_tester.write_devenv(
        "alfasim/app",
        """
        devenv.upstream = ["../calc", "../gui"]
        """,
    )

    ws = Workspace.from_starting_file(app_toml)
    assert set(ws.projects) == {
        "bootstrap",
        "xgui",
        "pvt",
        "core",
        "calc",
        "gui",
        "app",
    }
    assert ws.graph == {
        "bootstrap": [],
        "xgui": ["bootstrap"],
        "pvt": ["bootstrap"],
        "core": ["pvt"],
        "calc": ["core", "pvt"],
        "gui": ["xgui"],
        "app": ["calc", "gui"],
    }
    assert [x.name for x in ws.iter_upstream()] == [
        "app",
        "calc",
        "core",
        "gui",
        "pvt",
        "xgui",
        "bootstrap",
    ]
    assert [x.name for x in ws.iter_downstream()] == [
        "bootstrap",
        "xgui",
        "pvt",
        "gui",
        "core",
        "calc",
        "app",
    ]


def test_two_upstream_branches(devenv_tester: DevEnvTester) -> None:
    devenv_tester.write_devenv("bootstrap", "[devenv]")
    devenv_tester.write_devenv("bootstrap_2", "[devenv]")
    devenv_tester.write_devenv(
        "a",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )
    devenv_tester.write_devenv(
        "b",
        """
        devenv.upstream = ["../bootstrap"]
        """,
    )
    devenv_tester.write_devenv(
        "c",
        """
        devenv.upstream = ["../bootstrap_2"]
        """,
    )

    app_toml = devenv_tester.write_devenv(
        "app",
        """
        devenv.upstream = ["../a","../b","../c"]
        """,
    )

    ws = Workspace.from_starting_file(app_toml)
    assert set(ws.projects) == {"bootstrap", "bootstrap_2", "a", "b", "c", "app"}
    assert ws.graph == {
        "bootstrap": [],
        "bootstrap_2": [],
        "app": ["a", "b", "c"],
        "c": ["bootstrap_2"],
        "b": ["bootstrap"],
        "a": ["bootstrap"],
    }
    assert [x.name for x in ws.iter_upstream()] == [
        "app",
        "a",
        "b",
        "c",
        "bootstrap",
        "bootstrap_2",
    ]
    assert [x.name for x in ws.iter_downstream()] == [
        "bootstrap_2",
        "bootstrap",
        "c",
        "b",
        "a",
        "app",
    ]


def test_single_file(devenv_tester: DevEnvTester) -> None:
    app_toml = devenv_tester.write_devenv(
        "app",
        """
        [devenv]
        upstream = []
        """,
    )

    ws = Workspace.from_starting_file(app_toml)
    assert set(ws.projects) == {"app"}
    assert ws.graph == {"app": []}
    assert [x.name for x in ws.iter_upstream()] == ["app"]
    assert [x.name for x in ws.iter_downstream()] == ["app"]


def test_cycle(devenv_tester: DevEnvTester) -> None:
    devenv_tester.write_devenv(
        "a",
        """
        [devenv]
        upstream = ["../b"]
        """,
    )

    b_toml = devenv_tester.write_devenv(
        "b",
        """
        [devenv]
        upstream = ["../a"]
        """,
    )
    with pytest.raises(DevEnvError, match="DevEnv dependencies are in a cycle"):
        _ = Workspace.from_starting_file(b_toml)
