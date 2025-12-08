# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.trigger_openqa_in_openqa import app

runner = CliRunner()


def test_trigger_openqa_in_openqa(mocker: MockerFixture) -> None:
    mock_download_scenario = mocker.patch(
        "os_autoinst_scripts.trigger_openqa_in_openqa.download_scenario",
        return_value="scenario-definitions.yaml",
    )
    mock_find_image = mocker.patch(
        "os_autoinst_scripts._common.find_latest_published_tumbleweed_image",
        return_value="some.qcow2",
    )
    mock_httpx_get = mocker.patch("httpx.get")
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_create_snapshot = mocker.patch(
        "os_autoinst_scripts.trigger_openqa_in_openqa.create_devel_openqa_snapshot",
        return_value=0,
    )

    mock_httpx_get.return_value = MagicMock(raise_for_status=MagicMock(), content=b"scenario_content")
    mock_subprocess_run.return_value = MagicMock(stdout="job_id: 12345\n")

    result = runner.invoke(app)

    assert result.exit_code == 0
    mock_download_scenario.assert_called_once()
    mock_find_image.assert_called_once()
    mock_httpx_get.assert_called_once()
    mock_create_snapshot.assert_called_once()
    mock_subprocess_run.assert_called_once()


def test_trigger_openqa_in_openqa_full_run(mocker: MockerFixture) -> None:
    mock_download_scenario = mocker.patch(
        "os_autoinst_scripts.trigger_openqa_in_openqa.download_scenario",
        return_value="scenario-definitions.yaml",
    )
    mock_find_image = mocker.patch(
        "os_autoinst_scripts._common.find_latest_published_tumbleweed_image",
        return_value="some.qcow2",
    )
    mock_httpx_get = mocker.patch("httpx.get")
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_create_snapshot = mocker.patch(
        "os_autoinst_scripts.trigger_openqa_in_openqa.create_devel_openqa_snapshot",
        return_value=0,
    )

    mock_httpx_get.return_value = MagicMock(raise_for_status=MagicMock(), content=b"scenario_content")
    mock_subprocess_run.return_value = MagicMock(stdout="job_id: 12345\n")

    result = runner.invoke(app, ["--full-run"])

    assert result.exit_code == 0
    mock_download_scenario.assert_called_once()
    mock_find_image.assert_called_once()
    mock_httpx_get.assert_called_once()
    mock_create_snapshot.assert_called_once()
    mock_subprocess_run.assert_called_once()
