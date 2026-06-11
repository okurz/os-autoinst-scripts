<<<<<<< HEAD
# Copyright SUSE LLC
# ruff: noqa: S404, FBT001
"""Unit tests for monitor-openqa_job."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import logging
import pathlib
import subprocess
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock

import httpx
import pytest
import typer

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# Load the script dynamically as a module
rootpath = pathlib.Path(__file__).parent.parent.resolve()
path = rootpath / "monitor-openqa_job"
spec = importlib.util.spec_from_file_location(
    "monitor_job",
    path,
    loader=importlib.machinery.SourceFileLoader("monitor_job", str(path)),
)
assert spec is not None
assert spec.loader is not None
monitor_job = importlib.util.module_from_spec(spec)
sys.modules["monitor_job"] = monitor_job
spec.loader.exec_module(monitor_job)


def test_logging(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        monitor_job.log.info("info")
        monitor_job.log.warning("warn")
        monitor_job.log.error("err")
        monitor_job.log.debug("dbg")
    for log_msg in ["info", "warn", "err", "dbg"]:
        assert log_msg in caplog.text


@pytest.mark.parametrize(
    ("content", "exists", "expected"),
    [
        ('{"ids": [100]}', True, [100]),
        (None, False, typer.Exit),
        ("bad json", True, typer.Exit),
    ],
)
def test_load_job_ids(tmp_path: pathlib.Path, content: str | None, exists: bool, expected: Any) -> None:
    f = tmp_path / "job_post_response"
    if exists and content is not None:
        f.write_text(content)
    if expected is typer.Exit:
        with pytest.raises(typer.Exit) as exc:
            monitor_job.load_job_ids(str(f) if exists else "missing")
        assert exc.value.exit_code == 2
    else:
        assert monitor_job.load_job_ids(str(f)) == expected


def test_fetch_job_api() -> None:
    client, resp = MagicMock(spec=httpx.Client), Mock()
    resp.json.return_value = {"key": "val"}
    client.get.return_value = resp
    assert monitor_job.fetch_job_api(client, "http://host", {}, 2) == {"key": "val"}


@pytest.mark.parametrize(
    ("side_effects", "expected_calls"),
    [
        ([Mock(stdout="pkg1\npkg2-test\n"), Mock()], 2),
        (subprocess.CalledProcessError(1, "ls"), 1),
        ([Mock(stdout="pkg1\n"), subprocess.CalledProcessError(1, "del")], 2),
    ],
)
def test_delete_packages(mocker: MockerFixture, side_effects: Any, expected_calls: int) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run", side_effect=side_effects)
    monitor_job.delete_packages_from_obs_project("proj", "osc")
    assert mock_run.call_count == expected_calls


def test_extract_comment_ids() -> None:
    xml = '<comment id="12">test failed</comment>\n<comment id="34">ok</comment>'
    assert monitor_job.extract_comment_ids(xml) == ["12"]


@pytest.mark.parametrize(
    ("side_effects", "expected_calls"),
    [
        ([Mock(stdout='<comment id="9">test failed</comment>'), Mock()], 2),
        (subprocess.CalledProcessError(1, "api"), 1),
        ([Mock(stdout='<comment id="9">test failed</comment>'), subprocess.CalledProcessError(1, "del")], 2),
    ],
)
def test_delete_old_comments(mocker: MockerFixture, side_effects: Any, expected_calls: int) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run", side_effect=side_effects)
    monitor_job.delete_old_comments("osc", "pkg", "name")
    assert mock_run.call_count == expected_calls


@pytest.mark.parametrize("fails", [False, True])
def test_post_comment(mocker: MockerFixture, fails: bool) -> None:
    mock_run = mocker.patch("monitor_job.subprocess.run")
    if fails:
        mock_run.side_effect = subprocess.CalledProcessError(1, "post")
    monitor_job.post_comment("osc", "pkg", "name", "comment")
    mock_run.assert_called_once()


@pytest.mark.parametrize(
    ("side_effects", "expected_id", "expected_res", "expected_ver", "should_raise"),
    [
        ([{"job": {"id": 1, "state": "done", "result": "passed"}}], 1, "passed", "", False),
        (
            [
                {"job": {"id": 2, "state": "running"}},
                {"job": {"id": 2, "state": "done", "result": "failed", "settings": {"VERSION": "1"}}},
            ],
            2,
            "failed",
            "1",
            False,
        ),
        (Exception("error"), 0, "", "", True),
    ],
)
def test_monitor_single_job(
    mocker: MockerFixture,
    side_effects: Any,
    expected_id: int,
    expected_res: str,
    expected_ver: str,
    should_raise: bool,
) -> None:
    mocker.patch("time.sleep")
    mock_fetch = mocker.patch("monitor_job.fetch_job_api", side_effect=side_effects)
    client = MagicMock()
    if should_raise:
        with pytest.raises(typer.Exit) as exc:
            monitor_job.monitor_single_job(client, 1, "http://host", 2, 0)
        assert exc.value.exit_code == 1
    else:
        fid, res, ver = monitor_job.monitor_single_job(client, 1, "http://host", 2, 0)
        assert (fid, res, ver) == (expected_id, expected_res, expected_ver)
        assert mock_fetch.call_count == len(side_effects)


@pytest.mark.parametrize(
    ("job_res", "pkg_name", "comment_obs", "env_patch", "expected_exit"),
    [
        ((1, "passed", ""), "", "", {}, 0),
        ((1, "failed", "15"), "", "", {}, 1),
        ((1, "failed", "15"), "pkg", "1", {}, 1),
        ((1, "passed", ""), "", "", {"OPENQA_CLI_RETRIES": "invalid"}, 0),
        ((1, "passed", ""), "", "", {"PREFIX": "pre", "OSC": ""}, 0),
        ((1, "passed", ""), "", "", {"OSC": "custom"}, 0),
    ],
)
def test_main_flow(
    mocker: MockerFixture,
    job_res: tuple[int, str, str],
    pkg_name: str,
    comment_obs: str,
    env_patch: dict[str, str],
    expected_exit: int,
) -> None:
    mocker.patch("monitor_job.load_job_ids", return_value=[1])
    mocker.patch("monitor_job.monitor_single_job", return_value=job_res)
    mocker.patch("monitor_job.delete_packages_from_obs_project")
    mocker.patch("monitor_job.delete_old_comments")
    mocker.patch("monitor_job.post_comment")
    mocker.patch("monitor_job.httpx.Client")
    if env_patch:
        mocker.patch.dict("os.environ", env_patch)

    with pytest.raises(typer.Exit) as exc:
        monitor_job.main(obs_package_name=pkg_name, comment_on_obs=comment_obs)
    assert exc.value.exit_code == expected_exit


@pytest.mark.parametrize(
    ("pkg", "comment_obs", "expected_exit"),
    [
        ("pkg", "", 1),
        ("pkg", "1", 1),
    ],
)
def test_comment_on_failed_jobs(mocker: MockerFixture, pkg: str, comment_obs: str, expected_exit: int) -> None:
    mock_del = mocker.patch("monitor_job.delete_old_comments")
    mock_post = mocker.patch("monitor_job.post_comment")
    with pytest.raises(typer.Exit) as exc:
        monitor_job.comment_on_failed_jobs("osc", "package", pkg, comment_obs, [1], {"1": 1}, "24", "http://host")
    assert exc.value.exit_code == expected_exit
    if comment_obs:
        mock_del.assert_called_once()
        mock_post.assert_called_once()
||||||| parent of 378ecede (feat: rewrite monitor-openqa_job in Python)
=======
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
>>>>>>> 378ecede (feat: rewrite monitor-openqa_job in Python)
