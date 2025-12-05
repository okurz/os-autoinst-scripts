# Copyright SUSE LLC
import json

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.steps import app

runner = CliRunner()


def test_steps_no_failures(mocker: MockerFixture) -> None:
    step_context = json.dumps({"job1": {"outcome": "success"}, "job2": {"outcome": "success"}})
    result = runner.invoke(app, ["my-job", "owner/repo", "123", "--step-context", step_context])

    assert result.exit_code == 0
    assert "::set-output name=result::" in result.stdout
    assert "<p>" not in result.stdout


def test_steps_with_failures(mocker: MockerFixture) -> None:
    step_context = json.dumps({"job1": {"outcome": "success"}, "job2": {"outcome": "failure"}})
    result = runner.invoke(app, ["my-job", "owner/repo", "123", "--step-context", step_context])

    assert result.exit_code == 1
    assert "::set-output name=result::" in result.stdout
    assert "<p><b>There are failures in the GitHub Actions pipeline for repo" in result.stdout
    assert "<a href='https://github.com/owner/repo'>owner/repo</a></b></p>" in result.stdout
    assert "<table><tr><th>Job</th><th>Step</th><th>State</th></tr>" in result.stdout
    assert (
        "<tr><td><a href='https://github.com/owner/repo/actions/runs/123'>my-job</td><td>job2</td><td>failure</td></tr>"
        in result.stdout
    )
    assert "</table>" in result.stdout


def test_steps_invalid_json(mocker: MockerFixture) -> None:
    step_context = "invalid json"
    result = runner.invoke(app, ["my-job", "owner/repo", "123", "--step-context", step_context])

    assert result.exit_code == 1
    assert "Error: Invalid JSON for step_context" in result.stdout
    assert "::set-output name=result::" in result.stdout


def test_steps_no_context(mocker: MockerFixture) -> None:
    result = runner.invoke(app, ["my-job", "owner/repo", "123"])

    assert result.exit_code == 0
    assert "::set-output name=result::" in result.stdout
    assert "<p>" not in result.stdout
