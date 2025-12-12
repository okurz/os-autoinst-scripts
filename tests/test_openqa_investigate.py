# Copyright SUSE LLC
import json
from unittest.mock import ANY, MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_investigate import app

runner = CliRunner()


def test_investigate_passed_job(mocker: MockerFixture) -> None:
    mock_run_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_investigate.run_openqa_cli")
    mock_run_openqa_cli.return_value = json.dumps({"job": {"test": "some_test", "state": "done", "result": "passed"}})
    # mock_post_investigate = mocker.patch("os_autoinst_scripts.openqa_investigate.post_investigate")

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    mock_run_openqa_cli.assert_called_once()
    assert "Job 123 passed, no investigation needed." in result.stdout


def test_investigate_already_investigated(mocker: MockerFixture) -> None:
    mock_run_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_investigate.run_openqa_cli")
    mock_run_openqa_cli.side_effect = [
        json.dumps({
            "job": {"test": "some_test:investigate", "state": "done", "result": "failed"}
        }),
        json.dumps([{"id": 1, "text": "initial comment"}, {"id": 2, "text": "investigation comment"}]),
        MagicMock(return_value=None),  # This is for client_delete_job_comment
    ]
    mock_get_dependencies_ajax = mocker.patch(
        "os_autoinst_scripts.openqa_investigate.get_dependencies_ajax",
        return_value={},
    )
    mock_client_post_job_comment = mocker.patch("os_autoinst_scripts.openqa_investigate.client_post_job_comment", return_value={"id": 42})
    # mock_post_investigate = mocker.patch("os_autoinst_scripts.openqa_investigate.post_investigate")

    result = runner.invoke(app, ["123"])
    assert result.exit_code == 0
    mock_run_openqa_cli.assert_any_call(["api", "--host", ANY, "jobs/123"])  # This should be the first call
    mock_run_openqa_cli.assert_any_call(["api", "--host", ANY, "jobs/123/comments"])  # This should be the second call
    mock_run_openqa_cli.assert_any_call(["api", "--host", ANY, "-X", "DELETE", "jobs/123/comments/42"])  # This should be the third call.
    assert mock_run_openqa_cli.call_count == 3
    assert (
        "Skipping investigation of job 123: job cluster is already being investigated, \nsee comment on job 123\n"
        in result.stdout
    )


def test_investigate_clone_exists_no_force(mocker: MockerFixture) -> None:
    mock_run_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_investigate.run_openqa_cli")
    mock_run_openqa_cli.return_value = json.dumps({
        "job": {"test": "some_test", "state": "done", "result": "failed", "clone_id": 456}
    })
    mock_get_dependencies_ajax = mocker.patch(
        "os_autoinst_scripts.openqa_investigate.get_dependencies_ajax",
        return_value={},
    )
    mock_client_post_job_comment = mocker.patch("os_autoinst_scripts.openqa_investigate.client_post_job_comment", return_value={"id": 42})
    # mock_post_investigate = mocker.patch("os_autoinst_scripts.openqa_investigate.post_investigate")

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    assert "Job 123 already has a clone, skipping investigation." in result.stdout


def test_investigate_dependency_postponed(mocker: MockerFixture) -> None:
    mock_run_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_investigate.run_openqa_cli")
    mock_get_dependencies_ajax = mocker.patch(
        "os_autoinst_scripts.openqa_investigate.get_dependencies_ajax",
        return_value={"nodes": [{"id": 123, "state": "running"}]},
    )

    mock_run_openqa_cli.return_value = json.dumps({"job": {"test": "some_test", "state": "done", "result": "failed"}})

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 142
    assert "Postponing to investigate job 123" in result.stdout
    mock_get_dependencies_ajax.assert_called_once()
