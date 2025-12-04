# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_monitor_incompletes import app

runner = CliRunner()


def test_monitor_incompletes(mocker: MockerFixture) -> None:
    mock_ssh = mocker.patch("os_autoinst_scripts.openqa_monitor_incompletes.ssh")
    mock_ssh.return_value = MagicMock(stdout=b"1234|some-test\n")

    result = runner.invoke(app)

    assert result.exit_code == 0
    assert "https://openqa.opensuse.org/tests/1234 some-test" in result.stdout
    assert mock_ssh.call_count == 1
