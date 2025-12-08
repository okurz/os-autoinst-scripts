# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_incompletes_stats import app

runner = CliRunner()


def test_incompletes_stats(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_incompletes_stats.ssh")
    mock_ssh.return_value = MagicMock()

    result = runner.invoke(app)

    assert result.exit_code == 0
    assert mock_ssh.call_count == 1


def test_incompletes_stats_show_ids(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_incompletes_stats.ssh")
    mock_ssh.return_value = MagicMock()

    result = runner.invoke(app, ["--show-job-ids"])

    assert result.exit_code == 0
    assert mock_ssh.call_count == 1
    assert "array_agg(jobs.id)" in mock_ssh.call_args[0][2]


def test_incompletes_stats_show_workers(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_incompletes_stats.ssh")
    mock_ssh.return_value = MagicMock()

    result = runner.invoke(app, ["--show-worker-hosts"])

    assert result.exit_code == 0
    assert mock_ssh.call_count == 1
    assert "array(select distinct host from workers" in mock_ssh.call_args[0][2]
