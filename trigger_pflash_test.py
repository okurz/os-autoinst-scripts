#!/usr/bin/python3
# Copyright SUSE LLC
"""Trigger test to generate pflash vars image.

This script triggers an openQA test that generates a pflash vars image
for UEFI testing, using the latest published Tumbleweed image.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Annotated

import httpx
import sh
import typer
from sh import ErrorReturnCode
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

app = typer.Typer()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class OpenQAError(Exception):
    """Exception for openQA operations."""


@retry(
    stop=stop_after_attempt(12),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
def _fetch_json_with_retry(client: httpx.Client, url: str) -> dict:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        log.warning("HTTP error fetching '%s': %e", url, e)
        raise
    except json.JSONDecodeError as e:
        msg = f"Failed to parse JSON from {url}: {e}"
        raise OpenQAError(msg) from e


def _get_latest_published_builds(client: httpx.Client, tw_openqa_host: str, group_id: str) -> list[str]:
    url = f"{tw_openqa_host}/group_overview/{group_id}.json"
    log.debug("Fetching builds from '%s'", url)
    data = _fetch_json_with_retry(client, url)
    builds = [
        result["build"]
        for result in data.get("build_results", [])
        if result.get("tag", {}).get("description") == "published" and result.get("version") == "Tumbleweed"
    ]
    if not builds:
        msg = "Unable to find latest published Tumbleweed builds"
        raise OpenQAError(msg)
    return sorted(builds, reverse=True)


def _get_image_from_assets(tw_openqa_host: str, name_pattern: str) -> str | None:
    try:
        result = sh.Command("openqa-cli")("api", "--host", tw_openqa_host, "assets")
        assets_data = json.loads(str(result))
    except (ErrorReturnCode, json.JSONDecodeError) as e:
        log.warning("Failed to fetch assets: %s", e)
        return None
    matching_assets = [
        asset
        for asset in assets_data.get("assets", [])
        if re.search(name_pattern, asset.get("name", "")) and asset.get("size") is not None
    ]
    return matching_assets[0]["name"] if matching_assets else None


def find_latest_published_tumbleweed_image(
    tw_openqa_host: str,
    tw_group_id: str,
    arch: str,
    machine: str,
    image_type: str,
) -> str:
    with httpx.Client(timeout=30.0) as client:
        builds = _get_latest_published_builds(client, tw_openqa_host, tw_group_id)
    for build in builds:
        pattern = (
            f"Tumbleweed-NET-{arch}-Snapshot{build}-Media.iso$"
            if image_type == "iso"
            else f"Tumbleweed-{arch}-{build}-minimalx\\\\@{machine}.qcow"
        )
        log.debug("Searching for image matching pattern: %s", pattern)
        image = _get_image_from_assets(tw_openqa_host, pattern)
        if image:
            log.info("Found image: %s for build %s", image, build)
            return image
        log.warning(
            "Unable to determine %s image for Tumbleweed build '%s' (for architecture '%s' and machine '%s')",
            image_type,
            build,
            arch,
            machine,
        )
    log.error("No published %s image available for any build", image_type)
    sys.exit(2)


def _build_triggered_by_url() -> str | None:
    """Build TRIGGERED_BY URL from GitHub environment variables."""
    server_url = os.getenv("GITHUB_SERVER_URL")
    repo = os.getenv("GITHUB_REPOSITORY")
    ref_name = os.getenv("GITHUB_REF_NAME")
    script_name = Path(__file__).name
    return f"{server_url}/{repo}/blob/{ref_name}/{script_name}" if server_url and repo and ref_name else None


def _get_triggered_by() -> str | None:
    """Get TRIGGERED_BY value from environment or generate from GitHub vars."""
    triggered_by = os.getenv("TRIGGERED_BY")
    return triggered_by or _build_triggered_by_url()


@app.command()
def main(
    *,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print command without executing", envvar="dry_run")
    ] = False,
    target_host: str = typer.Option(
        "openqa.opensuse.org", "--target-host", help="Target openQA host", envvar="target_host"
    ),
    target_host_proto: str = typer.Option(
        "https", "--target-host-proto", help="Target host protocol", envvar="target_host_proto"
    ),
    tw_openqa_host: str = typer.Option(
        "https://openqa.opensuse.org", "--tw-openqa-host", help="Tumbleweed openQA host URL", envvar="tw_openqa_host"
    ),
    tw_group_id: str = typer.Option("1", "--tw-group-id", help="Tumbleweed group ID", envvar="tw_group_id"),
    arch: str = typer.Option("x86_64", "--arch", help="Architecture", envvar="arch"),
    machine: str = typer.Option("64bit", "--machine", help="Machine type", envvar="machine"),
    test: str = typer.Option("ovmf-resolution", "--test", help="Test name"),
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="openQA API key (discouraged, use openQA client config file or environment variable OPENQA_API_KEY)",
    ),
    api_secret: str = typer.Option(
        None,
        "--api-secret",
        help="openQA API secret (discouraged, use openQA client config file or environment variable OPENQA_API_SECRET)",
    ),
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
) -> None:
    """Trigger pflash test to generate vars image.

    This script finds the latest published Tumbleweed ISO image and triggers
    a test job that generates a pflash vars image for UEFI testing.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    log.info("Finding latest published Tumbleweed image...")
    image = find_latest_published_tumbleweed_image(tw_openqa_host, tw_group_id, arch, machine, "iso")
    cli_args = [
        "openqa-cli",
        "api",
        "--host",
        f"{target_host_proto}://{target_host}",
        "-X",
        "POST",
        "jobs",
        f"--apikey {api_key}" if api_key else "",
        f"--apisecret {api_secret}" if api_secret else "",
        f"TEST={test}@{arch}",
        "QEMUVGA=qxl",
        "UEFI=1",
        "UEFI_PFLASH_CODE=/usr/share/qemu/ovmf-x86_64-ms-code.bin",
        "UEFI_PFLASH_VARS=/usr/share/qemu/ovmf-x86_64-ms-vars.bin",
        "PUBLISH_PFLASH_VARS=ovmf-x86_64-ms-vars-800x600.qcow2",
        "DISTRI=openSUSE",
        "VERSION=Tumbleweed",
        "FLAVOR=NET",
        f"ARCH={arch}",
        "SCHEDULE=tests/boot/tianocore_set_resolution",
        f"ISO={image}",
    ]
    if triggered_by := _get_triggered_by():
        cli_args.append(f"TRIGGERED_BY={triggered_by}")
    if dry_run:
        log.info("DRY RUN: Would execute: %s", " ".join(filter(None, cli_args)))
        return
    log.info("Triggering openQA job...")
    log.debug("Command: %s", " ".join(cli_args))
    try:
        openqa_cli = sh.Command("openqa-cli")
        result = openqa_cli(*cli_args[1:])
        typer.echo(result)
        log.info("Job triggered successfully")
    except ErrorReturnCode as e:
        log.fatal("Failed to trigger job: %s", e)
        if e.stdout:
            typer.echo(e.stdout.decode())
        if e.stderr:
            typer.echo(e.stderr.decode(), file=sys.stderr)
        sys.exit(e.exit_code)


if __name__ == "__main__":
    app()
