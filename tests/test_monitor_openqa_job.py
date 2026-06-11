# Copyright SUSE LLC
# ruff: noqa: S404
"""Unit tests for monitor-openqa_job."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import pathlib
import subprocess
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import httpx
import pytest
import typer

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# Load the script as module "monitor_job"
rootpath = pathlib.Path(__file__).parent.parent.resolve()
loader = importlib.machinery.SourceFileLoader("monitor_job", f"{rootpath}/monitor-openqa_job")
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
monitor_job = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = monitor_job
loader.exec_module(monitor_job)


def test_colorize() -> None:
    stream = Mock()
    stream.isatty.return_value = True
    assert monitor_job.colorize("hello", "RED", stream, "always") == "REDhello\x1b[0m"
    assert monitor_job.colorize("hello", "RED", stream, "auto") == "REDhello\x1b[0m"

    stream.isatty.return_value = False
    assert monitor_job.colorize("hello", "RED", stream, "auto") == "hello"
    assert monitor_job.colorize("hello", "RED", stream, "never") == "hello"


def test_logging(mocker: MockerFixture) -> None:
    mock_print = mocker.patch("builtins.print")
    monitor_job.log_info("msg", "never")
    mock_print.assert_called_with("[info] msg")

    monitor_job.log_warn("msg", "never")
    mock_print.assert_called_with("[warn] msg", file=sys.stderr)

    monitor_job.log_error("msg", "never")
    mock_print.assert_called_with("[error] msg", file=sys.stderr)

    monitor_job.log_debug("msg", "never")
    mock_print.assert_called_with("[debug] msg", file=sys.stderr)


def test_load_job_ids_success(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "job_post_response"
    f.write_text(json.dumps({"ids": [100, 200]}))
    assert monitor_job.load_job_ids(str(f)) == [100, 200]


def test_load_job_ids_missing() -> None:
    with pytest.raises(typer.Exit) as exc:
        monitor_job.load_job_ids("nonexistent_file")
    assert exc.value.exit_code == 2


def test_load_job_ids_invalid(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "job_post_response"
    f.write_text("invalid json")
    with pytest.raises(typer.Exit) as exc:
        monitor_job.load_job_ids(str(f))
    assert exc.value.exit_code == 2


def test_fetch_job_api_success() -> None:
    client = MagicMock(spec=httpx.Client)
    resp = Mock()
    resp.json.return_value = {"key": "val"}
    client.get.return_value = resp

    res = monitor_job.fetch_job_api(client, "http://host", {}, 2)
    assert res == {"key": "val"}
    client.get.assert_called_once()
    resp.raise_for_status.assert_called_once()


def test_delete_packages_from_obs_project(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")

    res_ls = Mock()
    res_ls.stdout = "pkg1\npkg2-test\npkg3\n"
    mock_run.side_effect = [res_ls, Mock(), Mock()]

    monitor_job.delete_packages_from_obs_project("my_proj", "osc", "never")

    assert mock_run.call_count == 3
    args_ls = mock_run.call_args_list[0][0][0]
    assert args_ls == ["osc", "ls", "my_proj"]
    args_del1 = mock_run.call_args_list[1][0][0]
    assert "rdelete" in args_del1
    assert "pkg1" in args_del1
    args_del2 = mock_run.call_args_list[2][0][0]
    assert "rdelete" in args_del2
    assert "pkg3" in args_del2


def test_delete_packages_from_obs_project_empty_or_failed(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(1, "osc ls")

    monitor_job.delete_packages_from_obs_project("my_proj", "osc", "never")
    mock_run.assert_called_once()


def test_delete_packages_from_obs_project_delete_failed(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")
    res_ls = Mock()
    res_ls.stdout = "pkg1\n"
    mock_run.side_effect = [res_ls, subprocess.CalledProcessError(1, "osc rdelete", stderr="error deleting")]

    monitor_job.delete_packages_from_obs_project("my_proj", "osc", "never")
    assert mock_run.call_count == 2


def test_extract_comment_ids() -> None:
    xml_output = """
    <comment id="123">test failed</comment>
    <comment id="456">some other comment</comment>
    """
    assert monitor_job.extract_comment_ids(xml_output) == ["123"]


def test_delete_old_comments_success(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")

    res_api = Mock()
    res_api.stdout = '<comment id="999">test failed</comment>'
    mock_run.side_effect = [res_api, Mock()]

    monitor_job.delete_old_comments("osc", "package", "my_pkg", "never")
    assert mock_run.call_count == 2
    args_del = mock_run.call_args_list[1][0][0]
    assert "DELETE" in args_del
    assert "/comment/999" in args_del


def test_delete_old_comments_failed_query(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(1, "osc api")

    monitor_job.delete_old_comments("osc", "package", "my_pkg", "never")
    mock_run.assert_called_once()


def test_delete_old_comments_delete_failed(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")
    res_api = Mock()
    res_api.stdout = '<comment id="999">test failed</comment>'
    mock_run.side_effect = [res_api, subprocess.CalledProcessError(1, "osc api DELETE", stderr="error deleting")]

    monitor_job.delete_old_comments("osc", "package", "my_pkg", "never")
    assert mock_run.call_count == 2


def test_post_comment(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")
    monitor_job.post_comment("osc", "package", "my_pkg", "some comment", "never")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "--data=some comment" in args
    assert "/comments/package/my_pkg" in args


def test_post_comment_failed(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(1, "osc api POST", stderr="error posting")

    monitor_job.post_comment("osc", "package", "my_pkg", "comment", "never")
    mock_run.assert_called_once()


def test_monitor_single_job_success(mocker: MockerFixture) -> None:
    mock_fetch = mocker.patch("monitor_job.fetch_job_api")
    mock_fetch.return_value = {"job": {"id": 123, "state": "done", "result": "passed"}}
    client = MagicMock()

    final_id, result, _version = monitor_job.monitor_single_job(client, 123, "http://host", 2, 0, "never")
    assert final_id == 123
    assert result == "passed"
    mock_fetch.assert_called_once()


def test_monitor_single_job_cloned_and_done(mocker: MockerFixture) -> None:
    mock_fetch = mocker.patch("monitor_job.fetch_job_api")
    mock_fetch.side_effect = [
        {"job": {"id": 124, "state": "running"}},
        {"job": {"id": 124, "state": "done", "result": "failed", "settings": {"VERSION": "15.4"}}},
    ]
    mocker.patch("time.sleep")
    client = MagicMock()

    final_id, result, version = monitor_job.monitor_single_job(client, 123, "http://host", 2, 0, "never")
    assert final_id == 124
    assert result == "failed"
    assert version == "15.4"


def test_monitor_single_job_api_error(mocker: MockerFixture) -> None:
    mock_fetch = mocker.patch("monitor_job.fetch_job_api")
    mock_fetch.side_effect = Exception("API connection lost")
    client = MagicMock()

    with pytest.raises(typer.Exit) as exc:
        monitor_job.monitor_single_job(client, 123, "http://host", 2, 0, "never")
    assert exc.value.exit_code == 1


def test_main_all_passed(mocker: MockerFixture) -> None:
    mocker.patch("monitor_job.load_job_ids", return_value=[123])
    mocker.patch("monitor_job.monitor_single_job", return_value=(123, "passed", ""))
    mocker.patch("monitor_job.httpx.Client")

    with pytest.raises(typer.Exit) as exc:
        monitor_job.main()
    assert exc.value.exit_code == 0


def test_main_failed_no_comment(mocker: MockerFixture) -> None:
    mocker.patch("monitor_job.load_job_ids", return_value=[123])
    mocker.patch("monitor_job.monitor_single_job", return_value=(123, "failed", "15.4"))
    mock_del_pkgs = mocker.patch("monitor_job.delete_packages_from_obs_project")
    mocker.patch("monitor_job.httpx.Client")

    with pytest.raises(typer.Exit) as exc:
        monitor_job.main()
    assert exc.value.exit_code == 1
    mock_del_pkgs.assert_called_once()


def test_main_failed_with_obs_comment(mocker: MockerFixture) -> None:
    mocker.patch("monitor_job.load_job_ids", return_value=[123])
    mocker.patch("monitor_job.monitor_single_job", return_value=(123, "failed", "15.4"))
    mock_del_pkgs = mocker.patch("monitor_job.delete_packages_from_obs_project")
    mock_del_comments = mocker.patch("monitor_job.delete_old_comments")
    mock_post_comment = mocker.patch("monitor_job.post_comment")
    mocker.patch("monitor_job.httpx.Client")

    with pytest.raises(typer.Exit) as exc:
        monitor_job.main(obs_package_name="my_pkg", comment_on_obs="1")

    assert exc.value.exit_code == 1
    mock_del_pkgs.assert_called_once()
    mock_del_comments.assert_called_once()
    mock_post_comment.assert_called_once()
    assert "version=15.4" in mock_post_comment.call_args[0][3]


def test_main_invalid_retries_env(mocker: MockerFixture) -> None:
    mocker.patch.dict("os.environ", {"OPENQA_CLI_RETRIES": "invalid_int"})
    mocker.patch("monitor_job.load_job_ids", return_value=[123])
    mocker.patch("monitor_job.monitor_single_job", return_value=(123, "passed", ""))
    mocker.patch("monitor_job.httpx.Client")

    with pytest.raises(typer.Exit) as exc:
        monitor_job.main()
    assert exc.value.exit_code == 0


def test_main_with_prefix(mocker: MockerFixture) -> None:
    mocker.patch.dict("os.environ", {"PREFIX": "my_prefix", "OSC": ""})
    mocker.patch("monitor_job.load_job_ids", return_value=[123])
    mocker.patch("monitor_job.monitor_single_job", return_value=(123, "passed", ""))
    mocker.patch("monitor_job.httpx.Client")

    with pytest.raises(typer.Exit) as exc:
        monitor_job.main()
    assert exc.value.exit_code == 0


def test_main_with_preset_osc(mocker: MockerFixture) -> None:
    mocker.patch.dict("os.environ", {"OSC": "custom_osc_binary"})
    mocker.patch("monitor_job.load_job_ids", return_value=[123])
    mocker.patch("monitor_job.monitor_single_job", return_value=(123, "passed", ""))
    mocker.patch("monitor_job.httpx.Client")

    with pytest.raises(typer.Exit) as exc:
        monitor_job.main()
    assert exc.value.exit_code == 0
>>>>>>> fe95e6e6 (feat: rewrite monitor-openqa_job in Python)
