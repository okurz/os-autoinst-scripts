# Copyright SUSE LLC
from unittest.mock import MagicMock, call

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_advanced_retrigger_jobs import app

runner = CliRunner()


def test_retrigger_jobs(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_advanced_retrigger_jobs.ssh")
    mock_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_advanced_retrigger_jobs.openqa_cli")

    mock_ssh.return_value = MagicMock(stdout=b"123\n456\n789\n")

    result = runner.invoke(app, ["--failed-since", "2024-01-01"])

    assert result.exit_code == 0
    mock_ssh.assert_called_once()
    mock_openqa_cli.assert_called_once_with(
        "api",
        "--host",
        "openqa.opensuse.org",
        "-X",
        "POST",
        "jobs/restart",
        "jobs=123",
        "jobs=456",
        "jobs=789",
    )


def test_retrigger_jobs_with_comment(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_advanced_retrigger_jobs.ssh")
    mock_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_advanced_retrigger_jobs.openqa_cli")

    mock_ssh.return_value = MagicMock(stdout=b"123\n")

    result = runner.invoke(app, ["--failed-since", "2024-01-01", "--comment", "test-comment"])

    assert result.exit_code == 0
    mock_ssh.assert_called_once()
    mock_openqa_cli.assert_called_once_with(
        "api",
        "--host",
        "openqa.opensuse.org",
        "-X",
        "POST",
        "jobs/restart",
        "jobs=123",
        "comment=test-comment",
    )


def test_retrigger_jobs_dry_run(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_advanced_retrigger_jobs.ssh")
    mock_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_advanced_retrigger_jobs.openqa_cli")

    mock_ssh.return_value = MagicMock(stdout=b"123\n")

    result = runner.invoke(app, ["--failed-since", "2024-01-01", "--dry-run"])

    assert result.exit_code == 0
    mock_ssh.assert_called_once()
    mock_openqa_cli.assert_not_called()
    assert "Would restart jobs: jobs=123" in result.stdout
