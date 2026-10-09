# Copyright SUSE LLC
# ruff: file-ignore[boolean-type-hint-positional-argument]
"""Unit tests for s390x-qemu-zombie-reaper.py."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# Load the script as module "reaper" (the file is named `s390x-qemu-zombie-reaper.py`)
rootpath = pathlib.Path(__file__).parent.parent.resolve()
loader = importlib.machinery.SourceFileLoader("reaper", f"{rootpath}/s390x-qemu-zombie-reaper.py")
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
reaper = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = reaper
loader.exec_module(reaper)


def test_run_cmd(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.MagicMock(stdout="  some output \n", stderr="", returncode=0)
    assert reaper.run_cmd("echo test") == "some output"
    mock_run.assert_called_once()


def test_get_running_jobs(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("reaper.run_cmd")
    mock_run.return_value = '{"workers": [{"properties": {"WORKER_CLASS": "qemu_x86_64,s390zl12"}, "jobid": 123}]}'
    assert reaper.get_running_jobs("s390zl12.oqa.prg2.suse.org") == [123]


@pytest.mark.parametrize(
    ("dry_run", "jobs", "reboot_method", "expected_calls", "expected_cmd"),
    [
        (
            True,
            [123],
            "sysrq",
            [
                (
                    "[DRY-RUN] Would execute: ssh s390zl12.oqa.prg2.suse.org "
                    "\"sudo bash -c 'echo c > /proc/sysrq-trigger'\""
                ),
                "[DRY-RUN] Would execute: openqa-cli api --osd -X POST jobs/123/restart",
            ],
            None,
        ),
        (
            True,
            [123],
            "reboot",
            [
                ('[DRY-RUN] Would execute: ssh s390zl12.oqa.prg2.suse.org "sudo reboot"'),
                "[DRY-RUN] Would execute: openqa-cli api --osd -X POST jobs/123/restart",
            ],
            None,
        ),
        (
            False,
            [123],
            "sysrq",
            ["Triggering kernel crash dump (kdump) on s390zl12.oqa.prg2.suse.org...", "Retriggering job 123..."],
            "ssh s390zl12.oqa.prg2.suse.org \"sudo bash -c 'echo c > /proc/sysrq-trigger'\"",
        ),
        (
            False,
            [123],
            "reboot",
            ["Triggering reboot on s390zl12.oqa.prg2.suse.org...", "Retriggering job 123..."],
            'ssh s390zl12.oqa.prg2.suse.org "sudo reboot"',
        ),
    ],
)
def test_trigger_actions(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    dry_run: bool,
    jobs: list[int],
    reboot_method: str,
    expected_calls: list[str],
    expected_cmd: str | None,
) -> None:
    mock_run_cmd = mocker.patch("reaper.run_cmd")
    mocker.patch("reaper.wait_for_host", return_value=True)
    mocker.patch("time.sleep")
    method = reaper.RebootMethod(reboot_method)
    config = reaper.ReaperConfig(dry_run=dry_run, verbose=False, reboot_method=method)
    reaper.trigger_actions("s390zl12.oqa.prg2.suse.org", jobs, config)
    captured = capsys.readouterr().out
    for expected in expected_calls:
        assert expected in captured
    if not dry_run and expected_cmd:
        mock_run_cmd.assert_any_call(expected_cmd, check=False, verbose=False)


def test_handle_host_clean(mocker: MockerFixture) -> None:
    mock_run_cmd = mocker.patch("reaper.run_cmd")
    mock_run_cmd.return_value = ""
    mock_health = mocker.patch("reaper.check_libvirt_health", return_value=True)
    config = reaper.ReaperConfig(dry_run=False, verbose=False)
    reaper.handle_host("s390zl12.oqa.prg2.suse.org", config)
    mock_run_cmd.assert_called_once_with(
        "ssh s390zl12.oqa.prg2.suse.org pgrep -r Z qemu-system-s39", check=False, verbose=False
    )
    mock_health.assert_called_once_with("s390zl12.oqa.prg2.suse.org", config)


def test_handle_host_zombie_persistent(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mock_run_cmd = mocker.patch("reaper.run_cmd")
    mock_sleep = mocker.patch("time.sleep")
    mock_run_cmd.side_effect = ["12345", "12345 Fri Jul 17 2026 Z", "12345 Fri Jul 17 2026 Z", '{"workers": []}', ""]
    config = reaper.ReaperConfig(dry_run=False, verbose=False)
    reaper.handle_host("s390zl12.oqa.prg2.suse.org", config)
    captured = capsys.readouterr().out
    assert "!!! CRITICAL: Found persistent zombie processes on s390zl12.oqa.prg2.suse.org: 12345" in captured
    mock_sleep.assert_called_once_with(10)


def test_handle_host_zombie_persistent_reboot(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mock_run_cmd = mocker.patch("reaper.run_cmd")
    mock_sleep = mocker.patch("time.sleep")
    mock_run_cmd.side_effect = ["12345", "12345 Fri Jul 17 2026 Z", "12345 Fri Jul 17 2026 Z", '{"workers": []}', ""]
    config = reaper.ReaperConfig(dry_run=False, verbose=False, reboot_method=reaper.RebootMethod.REBOOT)
    reaper.handle_host("s390zl12.oqa.prg2.suse.org", config)
    captured = capsys.readouterr().out
    assert "Triggering reboot on s390zl12.oqa.prg2.suse.org..." in captured
    mock_sleep.assert_called_once_with(10)


def test_wait_for_host_success(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.MagicMock(returncode=0)
    mock_sleep = mocker.patch("time.sleep")
    assert reaper.wait_for_host("s390zl12.oqa.prg2.suse.org", reaper.ReaperConfig()) is True
    mock_sleep.assert_not_called()


def test_wait_for_host_timeout(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.MagicMock(returncode=255)
    mock_sleep = mocker.patch("time.sleep")
    mock_time = mocker.patch("time.time")
    # First time.time() returns start_time (0). Subsequent calls simulate elapsed time.
    # To timeout with max_wait_minutes=1, we need elapsed > 60.
    mock_time.side_effect = [0, 10, 30, 65]
    assert reaper.wait_for_host("s390zl12.oqa.prg2.suse.org", reaper.ReaperConfig(max_wait_minutes=1)) is False
    assert mock_sleep.call_count == 2


def test_trigger_actions_custom_limits(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mocker.patch("reaper.run_cmd")
    mock_wait = mocker.patch("reaper.wait_for_host", return_value=True)
    mock_sleep = mocker.patch("time.sleep")

    config = reaper.ReaperConfig(
        dry_run=False,
        verbose=False,
        max_wait_minutes=5,
        stability_delay_minutes=1,
    )
    reaper.trigger_actions(
        "s390zl12.oqa.prg2.suse.org",
        [123],
        config,
    )
    captured = capsys.readouterr().out
    assert "Waiting 1 minutes for host stability before restarting jobs..." in captured
    mock_wait.assert_called_once_with("s390zl12.oqa.prg2.suse.org", config)
    mock_sleep.assert_called_once_with(60)


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "side_effect", "verbose", "expected", "expected_out"),
    [
        (0, "Id Name State\n----------------\n1 openQA-SUT-1 running", "", None, False, True, ""),
        (reaper.SSH_ERR_CONNECT, "", "ssh: connect to host ...", None, False, True, ""),
        (1, "", "error: failed to connect to the hypervisor", None, False, False, ""),
        (0, "error: Disconnected from qemu:///system due to end of file", "", None, False, False, ""),
        (0, "", "", subprocess.TimeoutExpired("ssh ...", 15), False, False, ""),
        (
            0,
            "No domains.",
            "",
            None,
            True,
            True,
            "Checking libvirt health on s390zl12.oqa.prg2.suse.org...",
        ),
        (
            reaper.SSH_ERR_CONNECT,
            "",
            "ssh: connect",
            None,
            True,
            True,
            "Host s390zl12.oqa.prg2.suse.org is unreachable over SSH (exit code 255). Skipping libvirt health check.",
        ),
        (1, "boom", "", None, False, False, "output: boom"),
    ],
    ids=[
        "success",
        "unreachable_ssh",
        "failed_command",
        "error_in_output",
        "timeout",
        "verbose_success",
        "verbose_unreachable",
        "failed_with_output",
    ],
)
def test_check_libvirt_health(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    returncode: int,
    stdout: str,
    stderr: str,
    side_effect: Exception | None,
    verbose: bool,
    expected: bool,
    expected_out: str,
) -> None:
    mock_run = mocker.patch("subprocess.run")
    if side_effect:
        mock_run.side_effect = side_effect
    else:
        mock_run.return_value = mocker.MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)
    config = reaper.ReaperConfig(dry_run=False, verbose=verbose)
    assert reaper.check_libvirt_health("s390zl12.oqa.prg2.suse.org", config) is expected
    assert expected_out in capsys.readouterr().out


def test_handle_host_unhealthy_libvirt(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mock_run_cmd = mocker.patch("reaper.run_cmd")
    mock_run_cmd.side_effect = ["", '{"workers": []}', ""]  # pgrep, openqa-cli workers, and reboot
    mock_health = mocker.patch("reaper.check_libvirt_health", return_value=False)
    mocker.patch("reaper.wait_for_host", return_value=True)
    mocker.patch("time.sleep")
    config = reaper.ReaperConfig(dry_run=False, verbose=False)
    reaper.handle_host("s390zl12.oqa.prg2.suse.org", config)
    captured = capsys.readouterr().out
    assert "!!! CRITICAL: libvirt is unhealthy on s390zl12.oqa.prg2.suse.org" in captured
    assert "Triggering kernel crash dump (kdump) on s390zl12.oqa.prg2.suse.org..." in captured
    mock_health.assert_called_once_with("s390zl12.oqa.prg2.suse.org", config)


@pytest.mark.parametrize(
    ("verbose", "side_effect", "return_stdout", "expected", "expected_out"),
    [
        (True, None, "out\n", "out", "Executing: some cmd"),
        (
            False,
            subprocess.CalledProcessError(1, "some cmd", stderr="boom"),
            None,
            "",
            "Error executing command: some cmd",
        ),
    ],
    ids=["verbose_echo", "called_process_error"],
)
def test_run_cmd_variants(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    verbose: bool,
    side_effect: Exception | None,
    return_stdout: str | None,
    expected: str,
    expected_out: str,
) -> None:
    mock_run = mocker.patch("subprocess.run")
    if side_effect:
        mock_run.side_effect = side_effect
    else:
        mock_run.return_value = mocker.MagicMock(stdout=return_stdout)
    assert reaper.run_cmd("some cmd", verbose=verbose) == expected
    assert expected_out in capsys.readouterr().out


@pytest.mark.parametrize(
    ("workers_output", "expected"),
    [
        ("", []),
        ("not json", []),
        (
            (
                '{"workers": [{"properties": {"WORKER_CLASS": "qemu_x86_64"}, "jobid": 7}, '
                '{"properties": {"WORKER_CLASS": "s390zl12"}, "jobid": null}, '
                '{"properties": {}, "jobid": 9}]}'
            ),
            [],
        ),
    ],
    ids=["empty_output", "invalid_json", "no_match_and_null_jobid"],
)
def test_get_running_jobs_edge_cases(mocker: MockerFixture, workers_output: str, expected: list[int]) -> None:
    mocker.patch("reaper.run_cmd", return_value=workers_output)
    assert reaper.get_running_jobs("s390zl12.oqa.prg2.suse.org") == expected


@pytest.mark.parametrize(
    "verbose",
    [True, False],
    ids=["verbose_ssh_error", "quiet_ssh_error"],
)
def test_wait_for_host_ssh_error(mocker: MockerFixture, capsys: pytest.CaptureFixture[str], verbose: bool) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = [OSError("connection refused"), mocker.MagicMock(returncode=0)]
    mock_time = mocker.patch("time.time")
    mock_time.side_effect = [0, 0, 0]
    mocker.patch("time.sleep")
    config = reaper.ReaperConfig(verbose=verbose)
    assert reaper.wait_for_host("s390zl12.oqa.prg2.suse.org", config) is True
    captured = capsys.readouterr().out
    assert ("Checking host availability:" in captured) is verbose
    assert ("SSH check failed:" in captured) is verbose


@pytest.mark.parametrize(
    ("wait_result", "stability_delay_minutes", "expected_in", "expected_not_in"),
    [
        (
            False,
            3,
            "Host s390zl12.oqa.prg2.suse.org did not come back online. Skipping job retriggering.",
            "Retriggering job",
        ),
        (True, 0, "Retriggering job 123...", "Waiting"),
    ],
    ids=["host_never_responsive", "no_stability_delay"],
)
def test_trigger_actions_wait_variants(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    wait_result: bool,
    stability_delay_minutes: int,
    expected_in: str,
    expected_not_in: str,
) -> None:
    mocker.patch("reaper.run_cmd")
    mock_wait = mocker.patch("reaper.wait_for_host", return_value=wait_result)
    mocker.patch("time.sleep")
    config = reaper.ReaperConfig(dry_run=False, stability_delay_minutes=stability_delay_minutes)
    reaper.trigger_actions("s390zl12.oqa.prg2.suse.org", [123], config)
    captured = capsys.readouterr().out
    assert expected_in in captured
    assert expected_not_in not in captured
    mock_wait.assert_called_once_with("s390zl12.oqa.prg2.suse.org", config)


@pytest.mark.parametrize(
    ("verbose", "run_cmd_results", "expected_lines", "unexpected_lines"),
    [
        (
            True,
            ["12345", "12345 Fri Jul 17 2026 Z", "99999 Fri Jul 17 2026 Z"],
            [
                "Checking s390zl12.oqa.prg2.suse.org for zombies...",
                "Zombies on s390zl12.oqa.prg2.suse.org were transient or PIDs were reused.",
                "Host s390zl12.oqa.prg2.suse.org is clean and libvirt is healthy.",
            ],
            [],
        ),
        (
            False,
            ["12345", "12345 Fri Jul 17 2026 Z", "99999 Fri Jul 17 2026 Z"],
            [],
            ["CRITICAL", "transient"],
        ),
        (
            True,
            [""],
            [
                "Checking s390zl12.oqa.prg2.suse.org for zombies...",
                "Host s390zl12.oqa.prg2.suse.org is clean and libvirt is healthy.",
            ],
            [],
        ),
    ],
    ids=["transient_verbose", "transient_quiet", "clean_verbose"],
)
def test_handle_host_transient_zombies(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    verbose: bool,
    run_cmd_results: list[str],
    expected_lines: list[str],
    unexpected_lines: list[str],
) -> None:
    mock_run_cmd = mocker.patch("reaper.run_cmd")
    mock_run_cmd.side_effect = run_cmd_results
    mocker.patch("reaper.check_libvirt_health", return_value=True)
    mocker.patch("time.sleep")
    config = reaper.ReaperConfig(dry_run=False, verbose=verbose)
    reaper.handle_host("s390zl12.oqa.prg2.suse.org", config)
    captured = capsys.readouterr().out
    for line in expected_lines:
        assert line in captured
    for line in unexpected_lines:
        assert line not in captured


def test_reap_command(mocker: MockerFixture) -> None:
    mock_handle = mocker.patch("reaper.handle_host")
    reaper.reap(
        dry_run=True,
        verbose=True,
        reboot_method=reaper.RebootMethod.REBOOT,
        max_wait_minutes=1,
        stability_delay_minutes=0,
    )
    assert [call.args[0] for call in mock_handle.call_args_list] == list(reaper.HYPERVISORS)
    assert mock_handle.call_args_list[0].args[1] == reaper.ReaperConfig(
        dry_run=True,
        verbose=True,
        reboot_method=reaper.RebootMethod.REBOOT,
        max_wait_minutes=1,
        stability_delay_minutes=0,
    )


def test_main_entrypoint(mocker: MockerFixture) -> None:
    mocker.patch("sys.argv", ["s390x-qemu-zombie-reaper.py", "--dry-run"])
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.MagicMock(returncode=0, stdout="")
    script = f"{rootpath}/s390x-qemu-zombie-reaper.py"
    main_spec = importlib.util.spec_from_file_location(
        "__main__",
        script,
        loader=importlib.machinery.SourceFileLoader("__main__", script),
    )
    assert main_spec
    assert main_spec.loader
    main_mod = importlib.util.module_from_spec(main_spec)
    with pytest.raises(SystemExit):
        main_spec.loader.exec_module(main_mod)
