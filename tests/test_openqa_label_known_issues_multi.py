# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_label_known_issues_multi import app

runner = CliRunner()


def test_label_known_issues_multi(mocker: MockerFixture) -> None:
    mock_label_issue = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues_multi.label_issue"
    )

    result = runner.invoke(app, input="http://example.com/1\nhttp://example.com/2\n")

    assert result.exit_code == 0
    assert mock_label_issue.call_count == 2


def test_label_known_issues_multi_with_failures(mocker: MockerFixture) -> None:
    mock_label_issue = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues_multi.label_issue"
    )
    mock_label_issue.side_effect = [None, SystemExit(1)]

    result = runner.invoke(app, input="http://example.com/1\nhttp://example.com/2\n")

    assert result.exit_code == 0
    assert "1 unknown issues to be reviewed" in result.stdout
    assert "http://example.com/2" in result.stdout
    assert mock_label_issue.call_count == 2
