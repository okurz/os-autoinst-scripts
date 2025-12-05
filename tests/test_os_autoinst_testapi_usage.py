# Copyright SUSE LLC
import pathlib
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.os_autoinst_testapi_usage import app

runner = CliRunner()


def test_testapi_usage(mocker: MockerFixture) -> None:
    mock_rg = mocker.patch("os_autoinst_scripts.os_autoinst_testapi_usage.rg")
    mock_grep = mocker.patch("os_autoinst_scripts.os_autoinst_testapi_usage.grep")
    mock_cut = mocker.patch("os_autoinst_scripts.os_autoinst_testapi_usage.cut")
    mock_sort = mocker.patch("os_autoinst_scripts.os_autoinst_testapi_usage.sort")

    mock_sort.return_value = MagicMock(stdout=b"assert_screen\n")
    mock_rg.return_value = MagicMock(stderr=b"1 match\n")

    with pathlib.Path("testapi.pm").open("w", encoding="utf-8") as f:
        f.write("package testapi;\nsub assert_screen { }")

    result = runner.invoke(app, ["testapi.pm", "some/repo"])

    assert result.exit_code == 0
    assert "some/repo - assert_screen : 1 match" in result.stdout
    mock_rg.assert_called_once_with("--engine", "pcre2", "--stats", "(?<!_)assert_screen", "some/repo")
    mock_grep.assert_any_call(r"^sub \w+\s*[({:]", "testapi.pm")
    mock_cut.assert_called_once_with("-f2", "-d", " ")
    mock_sort.assert_called_once()
