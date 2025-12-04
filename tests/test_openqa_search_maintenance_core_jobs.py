# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_search_maintenance_core_jobs import app

runner = CliRunner()


def test_search_maintenance_core_jobs(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "job": {
                "settings": {"BUILD": "20240101-1", "VERSION": "15-SP4"},
                "children": {},
                "parents": {},
            }
        },
        text="",
    )

    result = runner.invoke(app, ["SUSE:Maintenance:12345:67890"])

    assert result.exit_code == 0
    assert "Maintenance: Single Incidents / Core Incidents" in result.stdout
    assert "Maintenance: Aggregated updates / Core Maintenance Updates" in result.stdout
    assert "Build checks" in result.stdout
