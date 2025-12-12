# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_label_known_issues_and_investigate_hook import app

runner = CliRunner()


def test_hook_passed_job(mocker: MockerFixture) -> None:
    mock_httpx_get = mocker.patch("httpx.get")
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_investigate_and_bisect = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues_and_investigate_hook.investigate_and_bisect"
    )

    mock_httpx_get.return_value = MagicMock(
        json=lambda: {"job": {"state": "done", "result": "passed"}},
        raise_for_status=MagicMock(),
    )

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    mock_httpx_get.assert_called_once()
    mock_investigate_and_bisect.assert_called_once_with("https://openqa.opensuse.org/tests/123")
    mock_subprocess_run.assert_not_called()


def test_hook_failed_job_bats_review(mocker: MockerFixture) -> None:
    mock_httpx_get = mocker.patch("httpx.get")
    mock_runcli = mocker.patch("os_autoinst_scripts.openqa_label_known_issues_and_investigate_hook.runcli")  # Patch runcli here
    mock_runcli.return_value = ""  # runcli returns string
    mock_label = mocker.patch("os_autoinst_scripts.openqa_label_known_issues_and_investigate_hook.label")
    mock_investigate_and_bisect = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues_and_investigate_hook.investigate_and_bisect"
    )

    mock_httpx_get.return_value = MagicMock(
        json=lambda: {
            "job": {
                "state": "done",
                "result": "failed",
                "settings": {"TEST": "podman_e2e"},
            }
        },
        raise_for_status=MagicMock(),
    )

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    mock_httpx_get.assert_called_once()
    mock_runcli.assert_called_once_with(  # Assert against runcli
        ["openqa-bats-review", "https://openqa.opensuse.org/tests/123"], check=True
    )
    mock_label.assert_not_called()
    mock_investigate_and_bisect.assert_not_called()


def test_hook_failed_job_label_and_bisect(mocker: MockerFixture) -> None:
    mock_httpx_get = mocker.patch("httpx.get")
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_label = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues_and_investigate_hook.label",
        return_value="https://openqa.opensuse.org/tests/123/issues/some_issue",
    )
    mock_investigate_and_bisect = mocker.patch(
        "os_autoinst_scripts.openqa_label_known_issues_and_investigate_hook.investigate_and_bisect"
    )

    mock_httpx_get.return_value = MagicMock(
        json=lambda: {
            "job": {
                "state": "done",
                "result": "failed",
                "settings": {"TEST": "other_test"},
            }
        },
        raise_for_status=MagicMock(),
    )

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    mock_httpx_get.assert_called_once()
    mock_subprocess_run.assert_not_called()
    mock_label.assert_called_once_with("https://openqa.opensuse.org/tests/123")
    mock_investigate_and_bisect.assert_called_once_with("https://openqa.opensuse.org/tests/123/issues/some_issue")
