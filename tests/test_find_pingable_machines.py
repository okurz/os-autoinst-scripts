# Copyright SUSE LLC
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from os_autoinst_scripts.find_pingable_machines import app

runner = CliRunner()


@patch("os_autoinst_scripts.find_pingable_machines.get_unused_machines")
@patch("subprocess.run")
def test_find_pingable_machines_ping_success(
    mock_subprocess_run: MagicMock, mock_get_unused_machines: MagicMock
) -> None:
    # Arrange
    mock_get_unused_machines.return_value = ["machine1.example.com", "machine2.example.com"]
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    # Act
    result = runner.invoke(app, catch_exceptions=False)

    # Assert
    assert "machine1.example.com up" in result.stdout
    assert "machine2.example.com up" in result.stdout
    assert result.exit_code == 1


@patch("os_autoinst_scripts.find_pingable_machines.get_unused_machines")
@patch("subprocess.run")
def test_find_pingable_machines_ping_failure(
    mock_subprocess_run: MagicMock, mock_get_unused_machines: MagicMock
) -> None:
    # Arrange
    mock_get_unused_machines.return_value = ["machine1.example.com", "machine2.example.com"]
    mock_subprocess_run.return_value = MagicMock(returncode=1)

    # Act
    result = runner.invoke(app, catch_exceptions=False)

    # Assert
    assert "machine1.example.com up" not in result.stdout
    assert "machine2.example.com up" not in result.stdout
    assert result.exit_code == 0


@patch("os_autoinst_scripts.find_pingable_machines.get_unused_machines")
def test_find_pingable_machines_no_machines(mock_get_unused_machines: MagicMock) -> None:
    # Arrange
    mock_get_unused_machines.return_value = []

    # Act
    result = runner.invoke(app, catch_exceptions=False)

    # Assert
    assert result.exit_code == 0
