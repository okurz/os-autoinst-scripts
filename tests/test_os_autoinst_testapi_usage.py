# Copyright SUSE LLC
import pathlib
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.os_autoinst_testapi_usage import app

runner = CliRunner()


def test_testapi_usage(mocker: MockerFixture) -> None:
    mock_grep_testapi = mocker.patch("os_autoinst_scripts.os_autoinst_testapi_usage.grep")
    mock_cut_testapi = mocker.patch("os_autoinst_scripts.os_autoinst_testapi_usage.cut")
    mock_sort_testapi = mocker.patch("os_autoinst_scripts.os_autoinst_testapi_usage.sort")

    mock_sort_testapi.return_value = MagicMock(stdout=b"assert_screen\n")
    mock_grep_testapi.return_value = MagicMock(stdout=b"sub assert_screen { }\n")
    mock_cut_testapi.return_value = MagicMock(stdout=b"assert_screen\n")

    with pathlib.Path("testapi.pm").open("w", encoding="utf-8") as f:
        f.write("package testapi;\nsub assert_screen { }")

    result = runner.invoke(app, ["testapi.pm", "some/repo"])

    assert result.exit_code == 0
    assert "some/repo - assert_screen : 1 match" in result.stdout
    mock_rg.assert_called_once_with("--engine", "pcre2", "--stats", "(?<!_)assert_screen", "some/repo")
    mock_grep.assert_any_call(r"^sub \w+\s*[({:]", "testapi.pm")
    mock_cut.assert_called_once_with("-f2", "-d", " ")
    mock_sort.assert_called_once()
