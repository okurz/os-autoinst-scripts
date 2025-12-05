# Copyright SUSE LLC
import json
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.openqa_schedule_mm_ping_test import app

runner = CliRunner()


def test_schedule_mm_ping_test(mocker: MockerFixture) -> None:
    mock_openqa_cli = mocker.patch("os_autoinst_scripts.openqa_schedule_mm_ping_test.openqa_cli")
    mock_openqa_cli.side_effect = [
        MagicMock(
            stdout=json.dumps({
                "jobs": [
                    {
                        "result": "passed",
                        "settings": {"BUILD": "20240101", "HDD_1": "some_hdd_image"},
                    }
                ]
            }).encode()
        ),
        MagicMock(),
    ]

    result = runner.invoke(app)

    assert result.exit_code == 0
    assert mock_openqa_cli.call_count == 2
    mock_openqa_cli.assert_any_call(
        "schedule",
        "--monitor",
        "--follow",
        "--host",
        "https://openqa.opensuse.org",
        "--param-file",
        mocker.ANY,  # We don't care about the exact path, just that it's there
        "DISTRI=opensuse",
        "VERSION=Tumbleweed",
        "FLAVOR=mm-monitoring",
        "ARCH=x86_64",
        mocker.ANY,  # BUILD date is dynamic
        "_GROUP_ID=0",
        "HDD_1=some_hdd_image",
    )
