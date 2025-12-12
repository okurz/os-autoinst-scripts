# Copyright SUSE LLC
from unittest.mock import call

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_investigate_multi import app

runner = CliRunner()


def test_investigate_multi(mocker: MockerFixture) -> None:
    mock_runcli = mocker.patch("os_autoinst_scripts.openqa_investigate_multi.runcli")
    mock_runcli.side_effect = ["", ""]  # Two calls, two empty strings (successful execution)

    result = runner.invoke(app, input="123\n456\n")
    assert result.exit_code == 0
    assert mock_runcli.call_count == 2
    mock_runcli.assert_has_calls([
        call(["openqa-investigate", "123"]),
        call(["openqa-investigate", "456"]),
    ])
