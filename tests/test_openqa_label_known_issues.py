# Copyright SUSE LLC
import json
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_label_known_issues import app

runner = CliRunner()


def test_label_known_issues(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "issues": [
                {
                    "id": 123,
                    "subject": "auto_review%3Asome_search_term",
                    "tracker": {"name": "SomeTracker"},
                }
            ],
            "job": {"state": "done", "result": "failed", "group_id": 1},
        },
        text="",
    )
    mock_label_on_issue = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues.label_on_issue",
        return_value=True,
    )

    result = runner.invoke(app, ["http://example.com/12345"])

    assert result.exit_code == 0
    assert mock_get.call_count == 2
    assert mock_label_on_issue.call_count > 0
