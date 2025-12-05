# Copyright SUSE LLC
import json
import subprocess
from unittest.mock import MagicMock, call

import pytest
from pytest_mock import MockerFixture

from os_autoinst_scripts._common import (
    job_ids,
    runcli,
    runjq,
    exp_retry,
    shorten_string,
    runcurl,
    openqa_api_get,
    comment_on_job,
    search_log,
    list_packages,
    delete_packages_from_obs_project,
    openqa_api_post,
    openqa_api_put,
)


def test_job_ids() -> None:
    content = '{"ids": [1, 2, 3]}'
    assert job_ids(content) == ["1", "2", "3"]


def test_job_ids_invalid_json() -> None:
    content = "invalid json"
    assert job_ids(content) == []


def test_runcli_success(mocker: MockerFixture) -> None:
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.return_value = MagicMock(stdout="success", stderr="")

    result = runcli(["echo", "hello"])
    assert result == "success"
    mock_subprocess_run.assert_called_once_with(
        ["echo", "hello"], capture_output=True, text=True, check=True
    )


def test_runcli_error(mocker: MockerFixture) -> None:
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["echo", "error"], stderr="some error"
    )

    with pytest.raises(subprocess.CalledProcessError):
        runcli(["echo", "error"])


def test_runjq_ids() -> None:
    content = '{"ids": [1, 2, 3]}'
    assert runjq(content, ".ids[]") == "1\n2\n3"


def test_runjq_job_result() -> None:
    content = '{"job": {"id": 123, "result": "passed"}}'
    assert runjq(content, ".job.result") == "passed"


def test_runjq_invalid_json() -> None:
    content = "invalid json"
    with pytest.raises(json.JSONDecodeError):
        runjq(content, ".job.result")


def test_exp_retry() -> None:
    assert exp_retry(3, 0) is True
    assert exp_retry(3, 1) is True
    assert exp_retry(3, 2) is True
    assert exp_retry(3, 3) is False


def test_shorten_string() -> None:
    assert shorten_string("a" * 100) == "a" * 100
    assert shorten_string("a" * 150) == f"{ 'a'*75 }...{'a'*75}"


def test_runcurl_success(mocker: MockerFixture) -> None:
    mock_httpx_get = mocker.patch("httpx.get")
    mock_httpx_get.return_value = MagicMock(text="success", raise_for_status=MagicMock())

    result = runcurl(["http://example.com"])
    assert result == "success"
    mock_httpx_get.assert_called_once_with("http://example.com")


def test_runcurl_retries(mocker: MockerFixture) -> None:
    mock_httpx_get = mocker.patch("httpx.get")
    mock_httpx_get.side_effect = [
        httpx.RequestError("error", request=httpx.Request("GET", "http://example.com")),
        MagicMock(text="success", raise_for_status=MagicMock()),
    ]
    mocker.patch("time.sleep")

    result = runcurl(["http://example.com"], exp_retries=1)
    assert result == "success"
    assert mock_httpx_get.call_count == 2


def test_openqa_api_get(mocker: MockerFixture) -> None:
    mock_runcli = mocker.patch("os_autoinst_scripts._common.runcli")
    mock_runcli.return_value = json.dumps({"job": {"id": 123}})

    result = openqa_api_get("jobs/123", "https://openqa.example.com")
    assert result == {"job": {"id": 123}}
    mock_runcli.assert_called_once_with(
        ["openqa-cli", "api", "--host", "https://openqa.example.com", "--json", "jobs/123"]
    )


def test_comment_on_job(mocker: MockerFixture) -> None:
    mock_log_info = mocker.patch("os_autoinst_scripts._common.log_info")
    comment_on_job(123, "test comment")
    mock_log_info.assert_called_once_with("Simulating comment on job 123: test comment")


def test_search_log(mocker: MockerFixture) -> None:
    mock_log_info = mocker.patch("os_autoinst_scripts._common.log_info")
    assert search_log(123, "search", "file.log") is True
    mock_log_info.assert_called_once_with("Simulating searching log file.log for 'search'")


def test_list_packages(mocker: MockerFixture) -> None:
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.return_value = MagicMock(stdout="package1\npackage2\n", stderr="")

    result = list_packages("my-project")
    assert result == ["package1", "package2"]


def test_delete_packages_from_obs_project(mocker: MockerFixture) -> None:
    mock_list_packages = mocker.patch("os_autoinst_scripts._common.list_packages")
    mock_subprocess_run = mocker.patch("subprocess.run")

    mock_list_packages.return_value = ["package1", "package2"]
    delete_packages_from_obs_project("my-project")
    mock_subprocess_run.assert_has_calls(
        [
            call(
                [
                    "osc",
                    "rdelete",
                    "-m",
                    "Cleaning up package1 from my-project",
                    "my-project",
                    "package1",
                ],
                check=True,
            ),
            call(
                [
                    "osc",
                    "rdelete",
                    "-m",
                    "Cleaning up package2 from my-project",
                    "my-project",
                    "package2",
                ],
                check=True,
            ),
        ]
    )


def test_openqa_api_post(mocker: MockerFixture) -> None:
    mock_runcli = mocker.patch("os_autoinst_scripts._common.runcli")
    mock_runcli.return_value = json.dumps({"id": 456})

    result = openqa_api_post("jobs", {"foo": "bar"}, "https://openqa.example.com")
    assert result == {"id": 456}
    mock_runcli.assert_called_once_with(
        ["openqa-cli", "api", "--host", "https://openqa.example.com", "-X", "POST", "jobs", "--json"],
        input='{"foo": "bar"}',
    )


def test_openqa_api_put(mocker: MockerFixture) -> None:
    mock_runcli = mocker.patch("os_autoinst_scripts._common.runcli")
    mock_runcli.return_value = json.dumps({"id": 456})

    result = openqa_api_put("jobs/123", {"foo": "bar"}, "https://openqa.example.com")
    assert result == {"id": 456}
    mock_runcli.assert_called_once_with(
        ["openqa-cli", "api", "--host", "https://openqa.example.com", "-X", "PUT", "jobs/123", "--json"],
        input='{"foo": "bar"}',
    )
