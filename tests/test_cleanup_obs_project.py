# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.cleanup_obs_project import app

runner = CliRunner()


def test_cleanup_obs_project_success(mocker: MockerFixture) -> None:
    def osc_side_effect(*args, **kwargs):
        if args[0] == "ls":
            return MagicMock(stdout=b"package1\npackage2\n")
        return MagicMock()

    mock_osc = mocker.patch("os_autoinst_scripts._common.osc", side_effect=osc_side_effect)

    result = runner.invoke(app, ["my-project", "I am sure"])

    assert result.exit_code == 0
    mock_osc.assert_any_call("ls", "my-project")
    mock_osc.assert_any_call("rdelete", "-m", "Cleaning up package1 from my-project", "my-project", "package1")
    mock_osc.assert_any_call("rdelete", "-m", "Cleaning up package2 from my-project", "my-project", "package2")


def test_cleanup_obs_project_no_confirmation(mocker: MockerFixture) -> None:
    mock_osc = mocker.patch("os_autoinst_scripts._common.osc")

    result = runner.invoke(app, ["my-project", "not sure"])

    assert result.exit_code == 2
    assert "Skipping, pass 'I am sure' as 2nd argument to confirm" in result.stdout
    mock_osc.assert_not_called()
