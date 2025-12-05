# Copyright SUSE LLC
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.obs_check_devel_openqa_leap_extra_dependencies import app

runner = CliRunner()


def test_check_reasons(mocker: MockerFixture) -> None:
    mock_osc = mocker.patch("os_autoinst_scripts.obs_check_devel_openqa_leap_extra_dependencies.osc")
    mock_osc.bake.return_value = mock_osc
    mock_osc.search.return_value = MagicMock(stdout=b"devel:openQA:Leap:15.5\ndevel:openQA:Leap:15.6")
    mock_osc.list.side_effect = [
        MagicMock(stdout=b"package1\npackage2"),
        MagicMock(stdout=b"package3"),
    ]
    mock_osc.api.side_effect = [
        MagicMock(stdout=b"Reason for linking:"),
        MagicMock(stdout=b"No reason"),
        MagicMock(stdout=b"Reason for linking:"),
    ]

    result = runner.invoke(app)

    assert result.exit_code == 1
    assert "No reason for devel:openQA:Leap:15.5/package2" in result.stdout
    assert mock_osc.search.call_count == 1
    assert mock_osc.list.call_count == 2
    assert mock_osc.api.call_count == 3


def test_check_reasons_all_ok(mocker: MockerFixture) -> None:
    mock_osc = mocker.patch("os_autoinst_scripts.obs_check_devel_openqa_leap_extra_dependencies.osc")
    mock_osc.bake.return_value = mock_osc
    mock_osc.search.return_value = MagicMock(stdout=b"devel:openQA:Leap:15.5\ndevel:openQA:Leap:15.6")
    mock_osc.list.side_effect = [
        MagicMock(stdout=b"package1\npackage2"),
        MagicMock(stdout=b"package3"),
    ]
    mock_osc.api.return_value = MagicMock(stdout=b"Reason for linking:")

    result = runner.invoke(app)

    assert result.exit_code == 0
    assert "No reason" not in result.stdout
    assert mock_osc.search.call_count == 1
    assert mock_osc.list.call_count == 2
    assert mock_osc.api.call_count == 3
