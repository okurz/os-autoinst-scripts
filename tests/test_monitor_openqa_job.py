# Copyright SUSE LLC
import json
from unittest.mock import MagicMock, call

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.monitor_openqa_job import app

runner = CliRunner()


def test_monitor_openqa_job_success(mocker: MockerFixture) -> None:
    mock_openqa_cli = mocker.patch("os_autoinst_scripts.monitor_openqa_job.openqa_cli")
    mock_job_ids = mocker.patch("os_autoinst_scripts.monitor_openqa_job.job_ids")
    mock_delete_packages = mocker.patch(
        "os_autoinst_scripts.monitor_openqa_job.delete_packages_from_obs_project"
    )

    mock_job_ids.return_value = ["123"]
    mock_openqa_cli.side_effect = [
        MagicMock(),  # openqa-cli monitor call
        MagicMock(  # openqa-cli api jobs/123 call
            stdout=json.dumps(
                {
                    "job": {
                        "id": 123,
                        "result": "passed",
                        "settings": {"VERSION": "15-SP4"},
                    }
                }
            ).encode(),
        ),
    ]

    # Create a dummy job_post_response file
    with open("job_post_response", "w") as f:
        f.write("123\n")

    result = runner.invoke(app, ["job_post_response"])

    assert result.exit_code == 0
    assert mock_job_ids.call_count == 1
    assert mock_openqa_cli.call_count == 2
    assert mock_delete_packages.call_count == 0


def test_monitor_openqa_job_failure(mocker: MockerFixture) -> None:
    mock_openqa_cli = mocker.patch("os_autoinst_scripts.monitor_openqa_job.openqa_cli")
    mock_job_ids = mocker.patch("os_autoinst_scripts.monitor_openqa_job.job_ids")
    mock_delete_packages = mocker.patch(
        "os_autoinst_scripts.monitor_openqa_job.delete_packages_from_obs_project"
    )
    mock_osc = mocker.patch("os_autoinst_scripts.monitor_openqa_job.osc")

    mock_job_ids.return_value = ["123"]
    mock_openqa_cli.side_effect = [
        MagicMock(),  # openqa-cli monitor call
        MagicMock(  # openqa-cli api jobs/123 call
            stdout=json.dumps(
                {
                    "job": {
                        "id": 123,
                        "result": "failed",
                        "settings": {"VERSION": "15-SP4"},
                    }
                }
            ).encode(),
        ),
    ]
    mock_osc.return_value = MagicMock(stdout=b"<comments></comments>")

    # Create a dummy job_post_response file
    with open("job_post_response", "w") as f:
        f.write("123\n")

    result = runner.invoke(
        app,
        [
            "job_post_response",
            "--obs-package-name",
            "test-package",
            "--comment-on-obs",
        ],
    )

    assert result.exit_code == 1
    assert "1 jobs did not pass:" in result.stdout
    assert mock_job_ids.call_count == 1
    assert mock_openqa_cli.call_count == 2
    assert mock_delete_packages.call_count == 1
    assert mock_osc.call_count == 2  # api for comments, api for posting comment
