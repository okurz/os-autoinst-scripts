#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script automates the submission of packages to OBS."""

from typing import Dict, List, Optional

import typer

from os_autoinst_scripts._common import (
    console,
    log_info,
    log_warn,
)

app = typer.Typer()

SRC_PROJECT = "devel:openQA"
DST_PROJECT = f"{SRC_PROJECT}:tested"
STAGING_PROJECT = f"{SRC_PROJECT}:testing"
SUBMIT_TARGET = "openSUSE:Factory"
SUBMIT_TARGET_EXTRA_PROJECT = "openSUSE:Backports"

XMLSTARLET = "xmlstarlet"  # Assuming xmlstarlet is installed and in PATH


def get_obs_sr_id(target: str, dst_project: str, package: str) -> Optional[str]:
    # Simplified, needs actual implementation based on xmlstarlet
    log_info(f"Simulating get_obs_sr_id for {target}/{dst_project}/{package}")
    return None


def get_obs_sr_id(target: str, dst_project: str, package: str) -> Optional[str]:
    # Simplified, needs actual implementation based on xmlstarlet
    log_info(f"Simulating get_obs_sr_id for {target}/{dst_project}/{package}")
    return None


def reenable_buildtime_services(package_dir: str) -> None:
    _run_cmd([
        "sed",
        "-i",
        "-e",
        's,mode="buildtime" mode="disabled",mode="buildtime",',
        f"{package_dir}/_service",
    ])


def wait_for_package_build(target: str, package: str, dst_project: str, dry_run: bool) -> bool:
    log_info(f"wait_for_package_build {target} {package}")
    # This needs actual OBS API calls, simulating for now
    if dry_run:
        console.print(f"Simulating waiting for build of {package} in {target}")
        return True
    return True


def make_obs_submit_request(package: str, target: str, version: str, dry_run: bool) -> bool:
    log_info(f"Simulating OBS submit request for {package} to {target} (version: {version})")
    if dry_run:
        console.print(f"Would run: osc sr -m 'Update to {version}' {target}")
        return True
    # Actual implementation with osc
    return True


def make_git_submit_request(package: str, target: str, version: str, branch: str, dry_run: bool) -> bool:
    log_info(f"Simulating Git submit request for {package} to {target} (version: {version}, branch: {branch})")
    if dry_run:
        console.print(f"Would run: git-obs commands for {package}")
        return True
    # Actual implementation with git-obs
    return True


def last_revision(project: str, package: str, submit_target: str) -> Optional[str]:
    # Placeholder for reading last revision from OBS
    log_info(f"Simulating last_revision for {project}/{package}")
    return None


def sync_changesrevision(src_project: str, package: str, target_rev: str, submit_target: str, dry_run: bool) -> None:
    log_info(f"Simulating sync_changesrevision for {src_project}/{package} to {target_rev}")
    if dry_run:
        console.print(f"Would sync changesrevision for {src_project}/{package}")


def get_spec_changes_in_requirements(package: str, project: str) -> bool:
    # Placeholder for checking spec changes
    return False


def generate_os_autoinst_distri_opensuse_deps_changelog(package_dir: str, package: str) -> None:
    log_info(f"Simulating changelog generation for {package_dir}/{package}")


def update_package(
    package: str,
    submit_target_list: List[str],
    dry_run: bool,
    git_branches: Dict[str, str],
    throttle_variables: Dict[str, str],
) -> List[str]:
    log_info(f"Updating package {package}")
    failed_packages: List[str] = []

    # Simplified implementation
    version = "1.0"  # Placeholder

    if not wait_for_package_build(SUBMIT_TARGET, package, DST_PROJECT, dry_run):
        failed_packages.append(package)
        return failed_packages

    for target in submit_target_list:
        if target == "none":
            continue

        # has_pending_submission is not implemented yet. Assuming it always returns true
        # if not has_pending_submission(package, target):
        #    continue

        log_info(f"## Ready to submit {package} to {target} ##")
        submit_cmd = make_obs_submit_request
        args = [package, target, version, dry_run]
        git_branch = git_branches.get(target)
        if git_branch:
            submit_cmd = make_git_submit_request
            args.append(git_branch)

        try:
            submit_cmd(*args)
        except Exception:
            failed_packages.append(package)

    return failed_packages


def has_pending_submission(
    package: str,
    target: str,
    git_branches: Dict[str, str],
    throttle_variables: Dict[str, str],
    throttle_days: int,
    throttle_days_leap_16: int,
) -> bool:
    # This is a complex function with external calls (git-obs, osc).
    # Placeholder for now, always returns True to allow submission.
    return True


def handle_auto_submit(package: str, dry_run: bool) -> List[str]:
    log_info(f"handle_auto_submit {package}")
    failed_packages: List[str] = []

    # Simplified implementation of auto submit logic
    # In real world, this would involve osc co, modifications, osc ci, etc.
    log_info(f"Simulating auto submit for {package}")

    return failed_packages


@app.command()
def main_app(
    submit_target_str: str = typer.Option(SUBMIT_TARGET, help="Submit target"),
    submit_target_extra_str: str = typer.Option(
        "openSUSE:Backports:SLE-15-SP6:Update,openSUSE:Leap:16.0",
        help="Extra submit targets (comma-separated)",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not perform any actions"),
    osc_poll_interval: int = typer.Option(2, help="osc poll interval"),
    osc_build_start_poll_tries: int = typer.Option(30, help="osc build start poll tries"),
    throttle_days: int = typer.Option(2, help="Throttle days"),
    throttle_days_leap_16: int = typer.Option(7, help="Throttle days for Leap 16"),
) -> None:
    """Automates the submission of packages to OBS."""
    submit_target_list = submit_target_str.split(",") + submit_target_extra_str.split(",")
    global failed_packages
    failed_packages = []

    git_branches: Dict[str, str] = {"openSUSE:Leap:16.0": "leap-16.0"}
    throttle_vars: Dict[str, str] = {"openSUSE:Leap:16.0": "throttle_days_leap_16"}

    # Placeholder for getting project packages. Assuming a fixed list for now.
    packages_to_submit = ["test-package-1", "test-package-2"]

    for package in packages_to_submit:
        failed_packages.extend(update_package(package, submit_target_list, dry_run, git_branches, throttle_vars))

    if failed_packages:
        log_warn("Failed packages:")
        for pkg in failed_packages:
            log_warn(f"- {pkg}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
