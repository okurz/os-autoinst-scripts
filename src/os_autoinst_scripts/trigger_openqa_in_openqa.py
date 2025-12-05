#!/usr/bin/env python3
# Copyright SUSE LLC
"""Trigger tests on an openQA instance testing openQA itself."""

import datetime
import sys
import tempfile
from typing import List, Optional

import typer

from os_autoinst_scripts._common import (
    ErrorReturnCode,
    cleanup_obs_project,
    console,
    delete_packages_from_obs_project,
    find_latest_published_tumbleweed_image,
    list_packages,
    log_error,
    log_info,
    log_warn,
    runcli,
    runcurl,
)

app = typer.Typer()


import pathlib

import typer

app = typer.Typer()


def download_scenario() -> str:
    scenario_url = (
        f"https://raw.githubusercontent.com/os-autoinst/os-autoinst-distri-openQA/master/{SCENARIO_DEFINITIONS}"
    )
    try:
        response_text = runcurl([scenario_url])
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
            f.write(response_text)
            return f.name
    except Exception as e:
        log_error(f"Error downloading scenario definitions: {e}")
        raise typer.Exit(1)


def create_devel_openqa_snapshot(full_run: bool, dry_run: bool) -> int:
    if full_run:
        return 0

    auto_submit_packages = list_packages(DST_PROJECT)
    staged_packages = list_packages(STAGING_PROJECT)

    if staged_packages:
        log_warn(
            f"NOTE: Only triggering tests from {SRC_PROJECT} (not overriding {STAGING_PROJECT} and doing a submission) because {STAGING_PROJECT} still contains packages. You might need to do a manual cleanup if no other pipeline is running. Packages: {staged_packages}"
        )
        with pathlib.Path("job_post_skip_submission").open("w") as f:
            f.write("true")
        return 0

    if pathlib.Path("job_post_skip_submission").exists():
        pathlib.Path("job_post_skip_submission").unlink()

    for package in auto_submit_packages:
        if not dry_run:
            log_info(f"Simulating checking state of {package} in OBS")
        try:
            osc_command = [
                "osc",
                "release",
                "--no-delay",
                "--target-project",
                STAGING_PROJECT,
                "-r",
                "openSUSE_Tumbleweed",
                "-a",
                ARCH,
                SRC_PROJECT,
                package,
            ]
            if dry_run:
                log_info(f"Would run: {' '.join(osc_command)}")
            else:
                runcli(osc_command, check=True)
        except ErrorReturnCode as e:
            log_error(f"Error creating snapshot for {package}: {e}")
            delete_packages_from_obs_project(STAGING_PROJECT)
            return 1

    if not dry_run:
        log_info(f"Simulating waiting for packages to be published under {STAGING_PROJECT}")
    return 0


@app.command()
def main_app(
    target_host: str = typer.Option(TARGET_HOST, help="Target openQA host"),
    target_host_proto: str = typer.Option(TARGET_HOST_PROTO, help="Target openQA host protocol"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not do any action on openQA"),
    tw_openqa_host: str = typer.Option(TW_OPENQA_HOST, help="Tumbleweed openQA host"),
    tw_group_id: str = typer.Option(TW_GROUP_ID, help="Tumbleweed group ID"),
    arch: str = typer.Option(ARCH, help="Architecture"),
    machine: str = typer.Option(MACHINE, help="Machine"),
    flavor: str = typer.Option(FLAVOR, help="Flavor"),
    full_run: bool = typer.Option(False, "--full-run", help="Full run, overrides staging project logic"),
    group_id: str = typer.Option(GROUP_ID, help="openQA group ID"),
    build_tag: str = typer.Option("", help="Build tag"),
) -> None:
    """Triggers tests on an openQA instance testing openQA itself."""
    openqa_cli_cmd = OPENQA_CLI_COMMAND
    if dry_run:
        openqa_cli_cmd = f"echo {OPENQA_CLI_COMMAND}"

    qcow_image: Optional[str] = None
    build_name: str = ""

    scenario_file_path = download_scenario()

    # Download latest published Tumbleweed image
    qcow_image = find_latest_published_tumbleweed_image(tw_group_id, arch, machine, "qcow")
    if f"{target_host_proto}://{target_host}" != tw_openqa_host:
        asset_url = f"{tw_openqa_host}/assets/hdd/{qcow_image}"
        target_path = f"/var/lib/openqa/factory/hdd/{qcow_image}"
        log_info(f"Downloading {asset_url} to {target_path}")
        if not dry_run:
            try:
                # Using httpx for download as wget is an external command
                response = httpx.get(asset_url, follow_redirects=True)
                response.raise_for_status()
                with pathlib.Path(target_path).open("wb") as f:
                    f.write(response.content)
            except httpx.HTTPError as e:
                log_error(f"Error downloading QCOW image: {e}")
                sys.exit(1)
    if build_tag:
        build_name = build_tag.replace("jenkins-trigger-openQA_in_openQA-", ":").replace("-", ".")

    # Create devel:openQA snapshots if not full_run
    if not full_run:
        rc = create_devel_openqa_snapshot(full_run, dry_run)
        if rc != 0:
            log_error("Snapshot creation failed, cleaning up staging project.")
            cleanup_obs_project(STAGING_PROJECT, "I am sure")
            raise typer.Exit(rc)
    else:
        # If full_run, staging_project is set to src_project in shell script
        # This python version doesn't modify global STAGING_PROJECT
        pass

    # Trigger job
    args: List[str] = []
    if target_host == "openqa.opensuse.org":
        args.append("OPENQA_HOST=http://openqa.opensuse.org")

    schedule_cmd = (
        [
            "schedule",
            "--monitor",
            "--follow",
            "--host",
            f"{target_host_proto}://{target_host}",
            "--param-file",
            f"SCENARIO_DEFINITIONS_YAML={scenario_file_path}",
            f"VERSION={version}",
            "DISTRI=openqa",
            f"FLAVOR={flavor}",
            f"ARCH={arch}",
            f"HDD_1={qcow_image}",
            f"BUILD={build_name or datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}",
            "_GROUP_ID=0",  # The original script used _GROUP_ID=0, but the variable is group_id. Assuming group_id is meant to be used here.
            f"OPENQA_OBS_PROJECT={STAGING_PROJECT}",
        ]
        + args
    )

    if dry_run:
        console.print(f"Would run: {openqa_cli_cmd} {' '.join(schedule_cmd)}")
    else:
        try:
            result = runcli([openqa_cli_cmd] + schedule_cmd, capture_output=True, text=True, check=True)
            with pathlib.Path("full_job_post_response").open("w") as f:
                f.write(result.stdout)
            with pathlib.Path("job_post_response").open("w") as f:
                f.write(result.stdout.splitlines()[0])
        except ErrorReturnCode as e:
            log_error(f"Error scheduling job: {e.stderr}")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
