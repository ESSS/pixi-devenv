from pathlib import Path

import pytest

from tests.devenv_tester import DevEnvTester


@pytest.fixture
def devenv_tester(tmp_path: Path) -> DevEnvTester:
    return DevEnvTester(tmp_path / "projects")
