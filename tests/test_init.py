from pathlib import Path

import pytest
from pytest_regressions.file_regression import FileRegressionFixture

from pixi_devenv.error import DevEnvError
from pixi_devenv.init import init_devenv


def test_init(tmp_path: Path, file_regression: FileRegressionFixture) -> None:
    tmp_path.joinpath("source/python").mkdir(parents=True)

    init_devenv(tmp_path)

    file_regression.check(
        tmp_path.joinpath("pixi.devenv.toml").read_text(), basename="devenv_expected", extension=".toml"
    )
    file_regression.check(
        tmp_path.joinpath("pixi.toml").read_text(), basename="pixi_expected", extension=".toml"
    )

    with pytest.raises(DevEnvError):
        init_devenv(tmp_path)
