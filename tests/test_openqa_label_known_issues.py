# Copyright SUSE LLC
import json
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_label_known_issues import app

runner = CliRunner()


def test_label_known_issues(mocker: MockerFixture) -> None:
    mock_runcli = mocker.patch("os_autoinst_scripts._common.runcli")

    def runcli_side_effect(args, **kwargs):
        if "openqa-cli" in args and "api" in args:
            return json.dumps({
                "job": {"state": "done", "result": "failed", "group_id": 1, "reason": "some reason"},
            })
        if "curl" in args:
            return "some log content"
        return MagicMock(stdout=b"", stderr=b"", returncode=0)
    mock_runcli.side_effect = runcli_side_effect
    mock_label_on_issue = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues.label_on_issue",
        return_value=True,
    )

    result = runner.invoke(app, ["http://example.com/12345"])

    assert result.exit_code == 0
    assert mock_label_on_issue.call_count > 0
