# Copyright SUSE LLC
from unittest.mock import call

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_investigate_multi import app

runner = CliRunner()


def test_investigate_multi(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")

    result = runner.invoke(app, input="123\n456\n")

    assert result.exit_code == 0
    assert mock_run.call_count == 2
    mock_run.assert_has_calls([call(["openqa-investigate", "123"], check=True), call(["openqa-investigate", "456"], check=True)])
