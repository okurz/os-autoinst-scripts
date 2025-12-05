# Copyright SUSE LLC
import json

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_investigate import app

runner = CliRunner()


def test_investigate_passed_job(mocker: MockerFixture) -> None:
    mock_run_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_investigate.run_openqa_cli")
    mock_run_openqa_cli.return_value = json.dumps({"job": {"test": "some_test", "state": "done", "result": "passed"}})
    mock_post_investigate = mocker.patch("os_autoinst_scripts.openqa_investigate.post_investigate")

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    mock_run_openqa_cli.assert_called_once()
    mock_post_investigate.assert_not_called()


def test_investigate_already_investigated(mocker: MockerFixture) -> None:
    mock_run_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_investigate.run_openqa_cli")
    mock_run_openqa_cli.return_value = json.dumps({
        "job": {"test": "some_test:investigate", "state": "done", "result": "failed"}
    })
    mock_post_investigate = mocker.patch("os_autoinst_scripts.openqa_investigate.post_investigate")

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    mock_run_openqa_cli.assert_called_once()
    mock_post_investigate.assert_called_once()


def test_investigate_clone_exists_no_force(mocker: MockerFixture) -> None:
    mock_run_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_investigate.run_openqa_cli")
    mock_run_openqa_cli.return_value = json.dumps({
        "job": {"test": "some_test", "state": "done", "result": "failed", "clone_id": 456}
    })
    mock_post_investigate = mocker.patch("os_autoinst_scripts.openqa_investigate.post_investigate")

    result = runner.invoke(app, ["123"])

    assert result.exit_code == 0
    assert "Job 123 already has a clone, skipping investigation." in result.stdout
    mock_post_investigate.assert_not_called()


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
