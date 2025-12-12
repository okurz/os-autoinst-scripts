# Copyright SUSE LLC

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.os_autoinst_obs_auto_submit import app

runner = CliRunner()


def test_obs_auto_submit_success(mocker: MockerFixture) -> None:
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.wait_for_package_build",
        return_value=True,
    )
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.make_obs_submit_request",
        return_value=True,
    )
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.has_pending_submission",
        return_value=False,
    )
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.get_obs_sr_id",
        return_value=None,
    )
    mocker.patch("os_autoinst_scripts.os_autoinst_obs_auto_submit.log_info")  # Mock log_info

    result = runner.invoke(app, ["main_app", "my-project"])

    assert result.exit_code == 0


def test_obs_auto_submit_failed_package(mocker: MockerFixture) -> None:
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.wait_for_package_build",
        return_value=True,
    )
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.make_obs_submit_request",
        side_effect=Exception("Submit failed"),
    )
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.has_pending_submission",
        return_value=False,
    )
    mocker.patch(
        "os_autoinst_scripts.os_autoinst_obs_auto_submit.get_obs_sr_id",
        return_value=None,
    )
    mock_log_warn = mocker.patch("os_autoinst_scripts.os_autoinst_obs_auto_submit.log_warn")

    result = runner.invoke(app, ["main_app", "my-project"])

    assert result.exit_code == 1
    mock_log_warn.assert_called_with("- test-package-1")
