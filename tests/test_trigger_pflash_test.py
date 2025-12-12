# Copyright SUSE LLC

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.trigger_pflash_test import app

runner = CliRunner()


def test_trigger_pflash_test(mocker: MockerFixture) -> None:
    mock_openqa_cli = mocker.patch("os_autoinst_scripts._common.openqa_cli")
    mock_find_image = mocker.patch("os_autoinst_scripts.trigger_pflash_test.find_latest_published_tumbleweed_image")
    mock_find_image.return_value = "some.iso"

    result = runner.invoke(app, ["--openqa-api-key", "dummy-key", "--openqa-api-secret", "dummy-secret"])

    assert result.exit_code == 0
    assert mock_openqa_cli.call_count == 1
    assert mock_find_image.call_count == 1


def test_trigger_pflash_test_dry_run(mocker: MockerFixture) -> None:
    mock_openqa_cli = mocker.patch("os_autoinst_scripts._common.openqa_cli")
    mock_find_image = mocker.patch("os_autoinst_scripts.trigger_pflash_test.find_latest_published_tumbleweed_image")
    mock_find_image.return_value = "some.iso"

    result = runner.invoke(
        app,
        [
            "--openqa-api-key",
            "dummy-key",
            "--openqa-api-secret",
            "dummy-secret",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Would trigger test:" in result.stdout
    assert mock_openqa_cli.call_count == 0
    assert mock_find_image.call_count == 1
