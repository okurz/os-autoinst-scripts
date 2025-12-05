# Copyright SUSE LLC
import json
import pathlib
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.backlog_set_due_date import app

runner = CliRunner()


def test_set_due_date(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_put = mocker.patch("httpx.put")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "issues": [
                {
                    "id": 1,
                    "priority": {"name": "Normal"},
                    "due_date": None,
                    "assigned_to": {"id": 1, "name": "foo"},
                    "status": {"name": "In Progress"},
                }
            ]
        },
    )

    result = runner.invoke(app, ["--redmine-api-key", "dummy-key"])

    assert result.exit_code == 0
    assert "Updating ticket 1" in result.stdout
    mock_put.assert_called_once()


def test_set_due_date_dry_run(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_put = mocker.patch("httpx.put")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "issues": [
                {
                    "id": 1,
                    "priority": {"name": "Normal"},
                    "due_date": None,
                    "assigned_to": {"id": 1, "name": "foo"},
                    "status": {"name": "In Progress"},
                }
            ]
        },
    )

    result = runner.invoke(app, ["--redmine-api-key", "dummy-key", "--dry-run"])

    assert result.exit_code == 0
    assert "Updating ticket 1" in result.stdout
    mock_put.assert_not_called()


def test_set_due_date_from_file(mocker: MockerFixture) -> None:
    mock_put = mocker.patch("httpx.put")
    issues = {
        "issues": [
            {
                "id": 1,
                "priority": {"name": "Normal"},
                "due_date": None,
                "assigned_to": {"id": 1, "name": "foo"},
                "status": {"name": "In Progress"},
            }
        ]
    }
    with pathlib.Path("test.json").open("w") as f:
        json.dump(issues, f)

    result = runner.invoke(
        app,
        ["main", "--redmine-api-key", "dummy-key", "--dry-run", "--issues-file", "test.json"],
    )

    assert result.exit_code == 0
    assert "Updating ticket 1" in result.stdout
    mock_put.assert_not_called()
