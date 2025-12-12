# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_query_for_job_label import app

runner = CliRunner()


def test_query_for_job_label(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_query_for_job_label.ssh")
    mock_ssh.return_value = MagicMock()

    result = runner.invoke(app, ["my-comment"])

    assert result.exit_code == 0
    assert mock_ssh.call_count == 2


def test_query_for_job_label_dry_run(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_query_for_job_label.ssh")

    result = runner.invoke(app, ["my-comment", "--dry-run"])

    assert result.exit_code == 0
    assert "Would ssh to openqa.opensuse.org and run query:" in result.stdout
    assert "Would ssh to openqa.suse.de and run query:" in result.stdout
    assert mock_ssh.call_count == 0
