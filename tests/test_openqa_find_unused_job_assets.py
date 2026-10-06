# Copyright SUSE LLC
# ruff: file-ignore[boolean-type-hint-positional-argument]
"""Unit tests for openqa-find-unused-job-assets."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import logging
import pathlib
import sys
from typing import TYPE_CHECKING, Any

import httpx
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

rootpath = pathlib.Path(__file__).parent.parent.resolve()
script_path = rootpath / "openqa-find-unused-job-assets"
spec = importlib.util.spec_from_file_location(
    "openqa_find_unused_job_assets",
    script_path,
    loader=importlib.machinery.SourceFileLoader("openqa_find_unused_job_assets", str(script_path)),
)
assert spec is not None
assert spec.loader is not None
unused_assets = importlib.util.module_from_spec(spec)
sys.modules["openqa_find_unused_job_assets"] = unused_assets
spec.loader.exec_module(unused_assets)


def test_parse_args_defaults() -> None:
    parsed = unused_assets.parse_args([])
    assert parsed.host == "https://openqa.opensuse.org"
    assert parsed.group is None
    assert parsed.build is None
    assert parsed.format == "text"
    assert parsed.timeout == pytest.approx(120.0)
    assert parsed.verbose == 1
    assert unused_assets.log.level == logging.ERROR


def test_parse_args_custom_values() -> None:
    args = [
        "-vv",
        "--host",
        "https://openqa.example.com",
        "--group",
        "42",
        "--build",
        "Build1234",
        "--format",
        "json",
        "--timeout",
        "30.5",
    ]
    parsed = unused_assets.parse_args(args)
    assert parsed.host == "https://openqa.example.com"
    assert parsed.group == 42
    assert parsed.build == "Build1234"
    assert parsed.format == "json"
    assert parsed.timeout == pytest.approx(30.5)
    assert parsed.verbose == 3
    assert unused_assets.log.level == logging.INFO


@pytest.mark.parametrize(
    ("v_args", "expected_verbose", "expected_level"),
    [
        ([], 1, logging.ERROR),
        (["-v"], 2, logging.WARNING),
        (["-vv"], 3, logging.INFO),
        (["-vvv"], 4, logging.DEBUG),
        (["-vvvv"], 5, logging.DEBUG),
        (["-vvvvv"], 6, logging.DEBUG),
    ],
    ids=["default-error", "v-warning", "vv-info", "vvv-debug", "vvvv-capped-debug", "vvvvv-capped-debug"],
)
def test_parse_args_verbosity(v_args: list[str], expected_verbose: int, expected_level: int) -> None:
    parsed = unused_assets.parse_args(v_args)
    assert parsed.verbose == expected_verbose
    assert unused_assets.log.level == expected_level


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("openSUSE-Tumbleweed.x86_64-1.0.0.vagrant.libvirt.box", True),
        ("openSUSE-Slowroll.x86_64.vagrant.virtualbox.box", True),
        ("custom.vagrant.box.box", True),
        ("openSUSE-Tumbleweed-DVD-x86_64-Current.iso", False),
        ("opensuse-tumbleweed-x86_64.qcow2", False),
        ("openSUSE.vagrant.tar.gz", False),
        ("vagrant.box", False),
        ("plain-archive.box", False),
    ],
    ids=[
        "tumbleweed-vagrant-libvirt-box",
        "slowroll-vagrant-virtualbox-box",
        "custom-vagrant-box-box",
        "iso-not-vagrant-box",
        "qcow2-not-vagrant-box",
        "vagrant-tar-gz-not-box",
        "vagrant-box-missing-middle-segment",
        "plain-box-missing-vagrant-segment",
    ],
)
def test_is_vagrant_box(filename: str, expected: bool) -> None:
    assert unused_assets.is_vagrant_box(filename) is expected


@pytest.mark.parametrize(
    ("job", "candidate_keys", "expected"),
    [
        (
            {"test": "vagrant_libvirt_test", "settings": {}},
            {"ASSET_1"},
            True,
        ),
        (
            {"test": "jeos", "settings": {"TEST": "vagrant-subtest"}},
            {"ASSET_1"},
            True,
        ),
        (
            {"name": "opensuse-Tumbleweed-vagrant-box-test@64bit", "test": "jeos", "settings": {}},
            {"ASSET_1"},
            True,
        ),
        (
            {"test": "jeos", "settings": {"VAGRANT": "1"}},
            {"ASSET_1"},
            True,
        ),
        (
            {"test": "jeos", "settings": {"DESKTOP": "vagrant_box"}},
            {"ASSET_1"},
            True,
        ),
        (
            {"test": "jeos", "settings": {"ASSET_1": "box.vagrant.libvirt.box"}},
            {"ASSET_1"},
            False,
        ),
        (
            {"test": "gnome", "name": "gnome-desktop@64bit", "settings": {"DESKTOP": "gnome"}},
            set(),
            False,
        ),
    ],
    ids=[
        "relates-via-test-suite-attribute",
        "relates-via-test-setting",
        "relates-via-job-name",
        "relates-via-setting-key",
        "relates-via-setting-value",
        "ignores-candidate-vagrant-asset-key",
        "unrelated-test-returns-false",
    ],
)
def test_relates_to_vagrant(job: dict[str, Any], candidate_keys: set[str], expected: bool) -> None:
    assert unused_assets.relates_to_vagrant(job, candidate_keys) is expected


@pytest.mark.parametrize(
    ("settings", "expected_flagged", "expected_reason"),
    [
        (
            {
                "ISO": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "opensuse-tumbleweed-x86_64.qcow2",
            },
            True,
            "ISO set while BOOT_HDD_IMAGE=1 and HDD_1 set",
        ),
        (
            {
                "ISO": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
                "BOOT_HDD_IMAGE": "true",
                "HDD_1": "opensuse-tumbleweed-x86_64.qcow2",
            },
            True,
            "ISO set while BOOT_HDD_IMAGE=1 and HDD_1 set",
        ),
        (
            {
                "ISO": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
                "BOOT_HDD_IMAGE": "0",
                "HDD_1": "opensuse-tumbleweed-x86_64.qcow2",
            },
            False,
            None,
        ),
        (
            {
                "ISO": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
                "BOOT_HDD_IMAGE": "1",
            },
            False,
            None,
        ),
        (
            {
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "opensuse-tumbleweed-x86_64.qcow2",
            },
            False,
            None,
        ),
    ],
    ids=[
        "iso-flagged-when-boot-hdd-image-is-1-and-hdd1-set",
        "iso-flagged-when-boot-hdd-image-is-true-and-hdd1-set",
        "iso-not-flagged-when-boot-hdd-image-is-0",
        "iso-not-flagged-when-hdd1-is-missing",
        "iso-not-flagged-when-iso-setting-is-missing",
    ],
)
def test_heuristic_iso_unused(
    settings: dict[str, Any],
    expected_flagged: bool,
    expected_reason: str | None,
) -> None:
    job = {"test": "gnome", "settings": settings}
    asset_sizes = {"openSUSE-Tumbleweed-DVD-x86_64-Current.iso": 4000000000}
    candidates = unused_assets.find_job_candidate_assets(job, asset_sizes)
    iso_candidates = [c for c in candidates if c.setting == "ISO"]

    if expected_flagged:
        assert len(iso_candidates) == 1
        assert iso_candidates[0].asset_name == "openSUSE-Tumbleweed-DVD-x86_64-Current.iso"
        assert iso_candidates[0].size == 4000000000
        assert iso_candidates[0].reason == expected_reason
    else:
        assert len(iso_candidates) == 0


@pytest.mark.parametrize(
    ("settings", "expected_settings"),
    [
        (
            {
                "ISO": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "opensuse-tumbleweed-x86_64.qcow2",
                "ASSET_256": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso.sha256",
            },
            ["ISO", "ASSET_256"],
        ),
        (
            {
                "ISO": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
                "BOOT_HDD_IMAGE": "0",
                "HDD_1": "opensuse-tumbleweed-x86_64.qcow2",
                "ASSET_256": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso.sha256",
            },
            [],
        ),
        (
            {
                "ISO": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "opensuse-tumbleweed-x86_64.qcow2",
            },
            ["ISO"],
        ),
    ],
    ids=[
        "asset-256-flagged-alongside-unused-iso",
        "asset-256-not-flagged-when-iso-is-in-use",
        "only-iso-flagged-when-asset-256-is-missing",
    ],
)
def test_heuristic_asset_256(settings: dict[str, Any], expected_settings: list[str]) -> None:
    job = {"test": "gnome", "settings": settings}
    asset_sizes = {
        "openSUSE-Tumbleweed-DVD-x86_64-Current.iso": 4000000000,
        "openSUSE-Tumbleweed-DVD-x86_64-Current.iso.sha256": 128,
    }
    candidates = unused_assets.find_job_candidate_assets(job, asset_sizes)
    flagged_settings = [c.setting for c in candidates]
    assert flagged_settings == expected_settings

    asset_256_candidates = [c for c in candidates if c.setting == "ASSET_256"]
    if "ASSET_256" in expected_settings:
        assert len(asset_256_candidates) == 1
        assert asset_256_candidates[0].size == 128
        assert asset_256_candidates[0].reason == "ASSET_256 (ISO checksum) set while ISO likely unused"


@pytest.mark.parametrize(
    ("job", "expected_flagged_keys"),
    [
        (
            {
                "test": "jeos",
                "settings": {
                    "ASSET_1": "openSUSE.x86_64.vagrant.libvirt.box",
                    "ASSET_2": "openSUSE.x86_64.vagrant.virtualbox.box",
                },
            },
            ["ASSET_1", "ASSET_2"],
        ),
        (
            {
                "test": "vagrant_libvirt_test",
                "settings": {
                    "ASSET_1": "openSUSE.x86_64.vagrant.libvirt.box",
                },
            },
            [],
        ),
        (
            {
                "test": "jeos",
                "settings": {
                    "ASSET_1": "openSUSE.x86_64.vagrant.libvirt.box",
                    "VAGRANT": "1",
                },
            },
            [],
        ),
        (
            {
                "test": "jeos",
                "settings": {
                    "ASSET_REPO": "non-vagrant-asset.iso",
                },
            },
            [],
        ),
    ],
    ids=[
        "vagrant-boxes-flagged-when-test-is-unrelated",
        "vagrant-boxes-not-flagged-when-test-name-relates-to-vagrant",
        "vagrant-boxes-not-flagged-when-setting-key-relates-to-vagrant",
        "non-vagrant-assets-not-flagged-by-vagrant-heuristic",
    ],
)
def test_heuristic_vagrant_boxes(job: dict[str, Any], expected_flagged_keys: list[str]) -> None:
    asset_sizes = {
        "openSUSE.x86_64.vagrant.libvirt.box": 500000000,
        "openSUSE.x86_64.vagrant.virtualbox.box": 600000000,
    }
    candidates = unused_assets.find_job_candidate_assets(job, asset_sizes)
    flagged = [c for c in candidates if c.setting.startswith("ASSET_") and c.setting != "ASSET_256"]
    assert [c.setting for c in flagged] == expected_flagged_keys
    for c in flagged:
        assert c.reason == f"{c.setting} containing .vagrant. box set while test name/settings do not relate to vagrant"


def test_find_job_candidate_assets_empty_settings() -> None:
    candidates = unused_assets.find_job_candidate_assets({}, {})
    assert candidates == []


def test_aggregate_candidates_and_sorting() -> None:
    asset_sizes = {
        "tw-dvd.iso": 4000000000,
        "tw-dvd.iso.sha256": 100,
        "tw.vagrant.libvirt.box": 500000000,
        "leap.iso": 3000000000,
    }
    jobs = [
        {
            "id": 101,
            "group": "openSUSE Tumbleweed",
            "group_id": 1,
            "test": "gnome",
            "settings": {
                "ISO": "tw-dvd.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "disk.qcow2",
                "ASSET_256": "tw-dvd.iso.sha256",
            },
        },
        {
            "id": 102,
            "group": "openSUSE Tumbleweed",
            "group_id": 1,
            "test": "gnome",
            "settings": {
                "ISO": "tw-dvd.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "disk.qcow2",
                "ASSET_256": "tw-dvd.iso.sha256",
            },
        },
        {
            "id": 103,
            "group": "openSUSE Tumbleweed",
            "group_id": 1,
            "test": "minimalx",
            "settings": {
                "ASSET_1": "tw.vagrant.libvirt.box",
            },
        },
        {
            "id": 104,
            "group": "openSUSE Leap",
            "group_id": 2,
            "test": "textmode",
            "settings": {
                "ISO": "leap.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "disk.qcow2",
            },
        },
        {
            "id": 105,
            "group": "openSUSE Tumbleweed",
            "group_id": 1,
            "test": "installation",
            "settings": {
                "ISO": "tw-dvd.iso",
                "BOOT_HDD_IMAGE": "0",
            },
        },
    ]

    aggregated = unused_assets.aggregate_candidates(jobs, asset_sizes)
    assert len(aggregated) == 3

    assert aggregated[0].group == "openSUSE Tumbleweed"
    assert aggregated[0].test_suite == "gnome"
    assert aggregated[0].job_count == 2
    assert aggregated[0].candidate_settings == ["ASSET_256", "ISO"]
    assert aggregated[0].total_bytes == 8000000200
    assert "ISO" in aggregated[0].reasons
    assert "ASSET_256" in aggregated[0].reasons

    assert aggregated[1].group == "openSUSE Leap"
    assert aggregated[1].test_suite == "textmode"
    assert aggregated[1].job_count == 1
    assert aggregated[1].total_bytes == 3000000000
    assert aggregated[1].candidate_settings == ["ISO"]

    assert aggregated[2].group == "openSUSE Tumbleweed"
    assert aggregated[2].test_suite == "minimalx"
    assert aggregated[2].job_count == 1
    assert aggregated[2].total_bytes == 500000000
    assert aggregated[2].candidate_settings == ["ASSET_1"]


def test_aggregate_candidates_fallback_names() -> None:
    asset_sizes = {"fallback.iso": 1000}
    jobs = [
        {
            "group_id": 99,
            "settings": {
                "ISO": "fallback.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "disk.qcow2",
            },
        },
        {
            "settings": {
                "ISO": "fallback.iso",
                "BOOT_HDD_IMAGE": "1",
                "HDD_1": "disk.qcow2",
            },
        },
    ]
    aggregated = unused_assets.aggregate_candidates(jobs, asset_sizes)
    assert len(aggregated) == 2
    groups = {item.group for item in aggregated}
    assert "Group 99" in groups
    assert "Unknown" in groups
    for item in aggregated:
        assert item.test_suite == "Unknown"


def test_format_text_with_candidates() -> None:
    candidates = [
        unused_assets.AggregatedCandidate(
            group="openSUSE Tumbleweed",
            group_id=1,
            test_suite="gnome",
            job_count=5,
            candidate_settings=["ASSET_256", "ISO"],
            total_bytes=20000000500,
            reasons={
                "ISO": "ISO set while BOOT_HDD_IMAGE=1 and HDD_1 set",
                "ASSET_256": "ASSET_256 (ISO checksum) set while ISO likely unused",
            },
        ),
    ]
    output = unused_assets.format_text(candidates)
    assert "Candidate unused job assets" in output
    assert "Candidates only" in output
    assert "openSUSE Tumbleweed (1)" in output
    assert "gnome" in output
    assert "ASSET_256, ISO" in output
    assert "20000000500" in output
    assert "Reasons:" in output
    assert "- ISO: ISO set while BOOT_HDD_IMAGE=1 and HDD_1 set" in output
    assert "- ASSET_256: ASSET_256 (ISO checksum) set while ISO likely unused" in output


def test_format_text_empty_candidates() -> None:
    output = unused_assets.format_text([])
    assert "Candidate unused job assets" in output
    assert "No candidates found." in output


def test_format_text_candidate_without_reasons() -> None:
    candidates = [
        unused_assets.AggregatedCandidate(
            group="openSUSE Tumbleweed",
            group_id=1,
            test_suite="gnome",
            job_count=1,
            candidate_settings=["ISO"],
            total_bytes=1000,
            reasons={},
        ),
    ]
    output = unused_assets.format_text(candidates)
    assert "Candidate unused job assets" in output
    assert "gnome" in output
    assert "Reasons:" not in output


def test_format_json_with_candidates() -> None:
    candidates = [
        unused_assets.AggregatedCandidate(
            group="openSUSE Tumbleweed",
            group_id=1,
            test_suite="gnome",
            job_count=5,
            candidate_settings=["ASSET_256", "ISO"],
            total_bytes=20000000500,
            reasons={"ISO": "ISO set while BOOT_HDD_IMAGE=1 and HDD_1 set"},
        ),
    ]
    output = unused_assets.format_json(candidates)
    data = json.loads(output)
    assert "candidates" in data
    assert "note" in data
    assert "Candidates only" in data["note"]
    assert len(data["candidates"]) == 1
    record = data["candidates"][0]
    assert record["group"] == "openSUSE Tumbleweed"
    assert record["group_id"] == 1
    assert record["test_suite"] == "gnome"
    assert record["job_count"] == 5
    assert record["candidate_settings"] == ["ASSET_256", "ISO"]
    assert record["total_bytes"] == 20000000500
    assert record["candidate"] is True


def test_format_json_empty_candidates() -> None:
    output = unused_assets.format_json([])
    data = json.loads(output)
    assert data["candidates"] == []
    assert "Candidates only" in data["note"]


def test_fetch_asset_sizes_pagination_and_error(mocker: MockerFixture) -> None:
    mock_client = mocker.MagicMock(spec=httpx.Client)

    def mock_get(url: str, params: dict[str, Any]) -> mocker.MagicMock:
        assert "/api/v1/assets" in url
        if params["offset"] == 0:
            mock_resp = mocker.MagicMock()
            mock_resp.json.return_value = {
                "assets": [{"name": f"asset_{i}.iso", "size": 1000 + i} for i in range(unused_assets.PAGE_LIMIT)]
            }
            return mock_resp
        if params["offset"] == unused_assets.PAGE_LIMIT:
            mock_resp = mocker.MagicMock()
            mock_resp.json.return_value = {
                "assets": [
                    {"name": "last_asset.iso", "size": 9999},
                    {"name": None, "size": 123},
                    {"name": "no_size", "size": None},
                ]
            }
            return mock_resp
        msg = "Offset exceeded"
        raise httpx.RequestError(msg)

    mock_client.get.side_effect = mock_get
    sizes = unused_assets.fetch_asset_sizes(mock_client, "https://openqa.test")
    assert len(sizes) == unused_assets.PAGE_LIMIT + 1
    assert sizes["asset_0.iso"] == 1000
    assert sizes["last_asset.iso"] == 9999


def test_fetch_asset_sizes_handles_failure(mocker: MockerFixture) -> None:
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    sizes = unused_assets.fetch_asset_sizes(mock_client, "https://openqa.test")
    assert sizes == {}


def test_fetch_jobs_pagination_and_filters(mocker: MockerFixture) -> None:
    mock_client = mocker.MagicMock(spec=httpx.Client)

    def mock_get(url: str, params: dict[str, Any]) -> mocker.MagicMock:
        assert "/api/v1/jobs" in url
        assert params["latest"] == 1
        assert params["groupid"] == 123
        assert params["build"] == "Build456"
        if params["offset"] == 0:
            mock_resp = mocker.MagicMock()
            mock_resp.json.return_value = {"jobs": [{"id": i} for i in range(unused_assets.PAGE_LIMIT)]}
            return mock_resp
        mock_resp = mocker.MagicMock()
        mock_resp.json.return_value = {"jobs": [{"id": 99999}]}
        return mock_resp

    mock_client.get.side_effect = mock_get
    jobs = unused_assets.fetch_jobs(
        mock_client,
        "https://openqa.test",
        group=123,
        build="Build456",
    )
    assert len(jobs) == unused_assets.PAGE_LIMIT + 1
    assert jobs[0]["id"] == 0
    assert jobs[-1]["id"] == 99999


def test_fetch_jobs_defaults(mocker: MockerFixture) -> None:
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = {"jobs": [{"id": 1}]}
    mock_client.get.return_value = mock_resp
    jobs = unused_assets.fetch_jobs(mock_client, "https://openqa.test")
    assert len(jobs) == 1
    mock_client.get.assert_called_once_with(
        "https://openqa.test/api/v1/jobs",
        params={"latest": 1, "limit": unused_assets.PAGE_LIMIT, "offset": 0},
    )


def test_main_text_mode_success(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mocker.patch("httpx.Client", return_value=mock_client)
    mock_client.__enter__.return_value = mock_client

    mocker.patch(
        "openqa_find_unused_job_assets.fetch_asset_sizes",
        return_value={"tw.iso": 2000},
    )
    mocker.patch(
        "openqa_find_unused_job_assets.fetch_jobs",
        return_value=[
            {
                "group": "openSUSE Tumbleweed",
                "group_id": 1,
                "test": "gnome",
                "settings": {"ISO": "tw.iso", "BOOT_HDD_IMAGE": "1", "HDD_1": "tw.qcow2"},
            }
        ],
    )

    exit_code = unused_assets.main(["--format", "text"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Candidate unused job assets" in captured.out
    assert "openSUSE Tumbleweed" in captured.out
    assert "gnome" in captured.out


def test_main_json_mode_success(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mocker.patch("httpx.Client", return_value=mock_client)
    mock_client.__enter__.return_value = mock_client

    mocker.patch(
        "openqa_find_unused_job_assets.fetch_asset_sizes",
        return_value={"tw.iso": 2000},
    )
    mocker.patch(
        "openqa_find_unused_job_assets.fetch_jobs",
        return_value=[
            {
                "group": "openSUSE Tumbleweed",
                "group_id": 1,
                "test": "gnome",
                "settings": {"ISO": "tw.iso", "BOOT_HDD_IMAGE": "1", "HDD_1": "tw.qcow2"},
            }
        ],
    )

    exit_code = unused_assets.main(["--format", "json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["group"] == "openSUSE Tumbleweed"


def test_main_api_http_error(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mocker.patch("httpx.Client", return_value=mock_client)
    mock_client.__enter__.return_value = mock_client

    mocker.patch(
        "openqa_find_unused_job_assets.fetch_jobs",
        side_effect=httpx.HTTPStatusError("404 Not Found", request=mocker.MagicMock(), response=mocker.MagicMock()),
    )

    exit_code = unused_assets.main([])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: API request failed" in captured.err


def test_logging_progress_and_debugging(mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
    unused_assets.parse_args(["-vvv"])
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = {"assets": [{"name": "test.iso", "size": 1234}]}
    mock_client.get.return_value = mock_resp

    with caplog.at_level(logging.DEBUG, logger="openqa-find-unused-job-assets"):
        unused_assets.fetch_asset_sizes(mock_client, "https://openqa.test")
        assert "Fetching asset sizes from https://openqa.test" in caplog.text
        assert "Fetched 1 asset sizes in total" in caplog.text

    caplog.clear()
    mock_jobs_resp = mocker.MagicMock()
    mock_jobs_resp.json.return_value = {
        "jobs": [
            {
                "id": 1,
                "group": "G",
                "test": "T",
                "settings": {"ISO": "test.iso", "BOOT_HDD_IMAGE": "1", "HDD_1": "h.qcow2"},
            }
        ]
    }
    mock_client.get.return_value = mock_jobs_resp

    with caplog.at_level(logging.DEBUG, logger="openqa-find-unused-job-assets"):
        jobs = unused_assets.fetch_jobs(mock_client, "https://openqa.test")
        assert "Fetching latest jobs from https://openqa.test" in caplog.text
        assert "Fetched 1 jobs (offset 0)" in caplog.text
        assert "Fetched 1 jobs in total" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="openqa-find-unused-job-assets"):
        unused_assets.aggregate_candidates(jobs, {"test.iso": 1234})
        assert "Analyzing 1 jobs for candidate unused assets" in caplog.text
        assert "Job 1 (G, test: T): found 1 candidate unused asset(s)" in caplog.text
        assert "Found 1 candidate groups with unused assets" in caplog.text
