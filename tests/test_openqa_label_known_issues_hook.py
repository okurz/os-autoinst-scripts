# Copyright SUSE LLC

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_label_known_issues_hook import app

runner = CliRunner()


def test_label_known_issues_hook(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")

    result = runner.invoke(app, ["12345"])

    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["openqa-label-known-issues-multi"],
        input="https://openqa.opensuse.org/tests/12345",
        text=True,
        check=True,
    )
