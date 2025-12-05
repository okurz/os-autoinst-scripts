# Copyright SUSE LLC
from unittest.mock import MagicMock, call

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.cleanup_obs_project import app

runner = CliRunner()


def test_cleanup_obs_project_success(mocker: MockerFixture) -> None:
    mock_osc = mocker.patch("os_autoinst_scripts.cleanup_obs_project.osc")
    mock_osc.ls.return_value = MagicMock(stdout=b"package1\npackage2\n")

    result = runner.invoke(app, ["my-project", "I am sure"])

    assert result.exit_code == 0
    mock_osc.ls.assert_called_once_with("my-project")
    mock_osc.rdelete.assert_has_calls(
        [
            call("-m", "Cleaning up package1 from my-project", "my-project", "package1"),
            call("-m", "Cleaning up package2 from my-project", "my-project", "package2"),
        ]
    )


def test_cleanup_obs_project_no_confirmation(mocker: MockerFixture) -> None:
    mock_osc = mocker.patch("os_autoinst_scripts.cleanup_obs_project.osc")

    result = runner.invoke(app, ["my-project", "not sure"])

    assert result.exit_code == 2
    assert "Skipping, pass 'I am sure' as 2nd argument to confirm" in result.stdout
    mock_osc.ls.assert_not_called()
