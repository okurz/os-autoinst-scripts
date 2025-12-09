# Copyright SUSE LLC
from unittest.mock import MagicMock

import httpx
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.backlog_check_wip_limit import app

runner = CliRunner()


def test_wip_limit_not_exceeded(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "issues": [
                {"status": {"name": "In Progress"}},
                {"status": {"name": "In Progress"}},
            ]
        },
    )

    result = runner.invoke(app, ["--redmine-api-key", "dummy-key", "--wip-limit", "3"])

    assert result.exit_code == 0
    assert "WIP limit not exceeded" in result.stdout


def test_wip_limit_exceeded(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "issues": [
                {"status": {"name": "In Progress"}},
                {"status": {"name": "In Progress"}},
                {"status": {"name": "In Progress"}},
            ]
        },
    )

    result = runner.invoke(app, ["--redmine-api-key", "dummy-key", "--wip-limit", "2"])

    assert result.exit_code == 1
    assert "WIP limit exceeded" in result.stdout


def test_redmine_error(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_get.side_effect = httpx.RequestError(
        "Something went wrong", request=httpx.Request("GET", "http://example.com")
    )

    result = runner.invoke(app, ["--redmine-api-key", "dummy-key", "--wip-limit", "2"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
