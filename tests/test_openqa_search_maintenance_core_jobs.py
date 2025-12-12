# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_search_maintenance_core_jobs import app

runner = CliRunner()


def test_search_maintenance_core_jobs(mocker: MockerFixture) -> None:
    mock_get = mocker.patch("httpx.get")
    mock_get.side_effect = [
        MagicMock(  # For incident_settings_url
            status_code=200,
            json=lambda: [
                {"settings": {"BUILD": "20240101-1", "VERSION": "15-SP4"}}
            ]
        ),
        MagicMock(  # For overview_url
            status_code=200,
            json=lambda: [
                {
                    "id": 123,
                    "settings": {"BUILD": "20240101-1", "VERSION": "15-SP4"},
                    "children": {},
                    "parents": {},
                }
            ],
            text="",
        ),
        MagicMock(  # For running_url
            status_code=200,
            json=list,
            text="",
        ),
        MagicMock(  # For failed_url
            status_code=200,
            json=list,
            text="",
        ),
        MagicMock(  # For incident_settings_url in search_maintenance_aggregated
            status_code=200,
            json=lambda: [
                {"settings": {"BUILD": "20240101-1", "VERSION": "15-SP4"}}
            ]
        ),
        MagicMock(  # For download.suse.de/ibs/.../repomd.xml
            status_code=200,
            text="<revision>20240101-1</revision>",
        ),
        MagicMock(  # For overview_url in search_maintenance_aggregated
            status_code=200,
            json=lambda: [
                {
                    "id": 123,
                    "settings": {"BUILD": "20240101-1", "VERSION": "15-SP4", "some_TEST_ISSUES": "SUSE:Maintenance:12345:67890"},
                    "children": {},
                    "parents": {},
                }
            ],
            text="",
        ),
        MagicMock(  # For job_details_url in search_maintenance_aggregated
            status_code=200,
            json=lambda: {
                "job": {
                    "id": 123,
                    "settings": {"BUILD": "20240101-1", "VERSION": "15-SP4", "some_TEST_ISSUES": "SUSE:Maintenance:12345:67890"},
                    "children": {},
                    "parents": {},
                }
            },
            text="",
        ),
        MagicMock(  # For running_url in search_maintenance_aggregated
            status_code=200,
            json=list,
            text="",
        ),
        MagicMock(  # For failed_url in search_maintenance_aggregated
            status_code=200,
            json=list,
            text="",
        ),
        MagicMock(  # For index_url in search_build_checks
            status_code=200,
            text='<a href="some_log.log">some_log.log</a>',
        ),
        MagicMock(  # For log_url in search_build_checks
            status_code=200,
            text="some line\n+ exit 0",
        ),
    ]

    result = runner.invoke(app, ["SUSE:Maintenance:12345:67890"])

    assert result.exit_code == 0
    assert "Maintenance: Single Incidents / Core Incidents" in result.stdout
    assert "Maintenance: Aggregated updates / Core Maintenance Updates" in result.stdout
    assert "Build checks" in result.stdout
