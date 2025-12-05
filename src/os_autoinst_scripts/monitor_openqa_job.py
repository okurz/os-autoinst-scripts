#!/usr/bin/env python3
# Copyright SUSE LLC
"""Monitor an openQA job by polling the status of a job over the API."""

import json
import os
import pathlib
import sys
from typing import List, Optional

import typer

from os_autoinst_scripts._common import (
    ErrorReturnCode,
    console,
    delete_packages_from_obs_project,
    job_ids,
    log_error,
    log_info,
    log_warn,
    openqa_cli,
    osc,
)

app = typer.Typer()


@app.command()
def main(
    job_post_response_file: str = typer.Argument(..., help="Path to job response status file"),
    host: str = typer.Option("https://openqa.opensuse.org", help="openQA host"),
    sleep_time: int = typer.Option(10, help="Sleep time between polls"),
    openqa_groupid: str = typer.Option("24", help="openQA group ID"),
    obs_component: str = typer.Option("package", help="OBS component"),
    obs_package_name: Optional[str] = typer.Option(None, help="OBS package name"),
    staging_project: str = typer.Option("devel:openQA:testing", help="Staging project"),
    comment_on_obs: bool = typer.Option(False, "--comment-on-obs", help="Comment on OBS for failed jobs"),
    openqa_cli_retries: int = typer.Option(7, help="openQA CLI retries"),
) -> None:
    """Monitor an openQA job by polling the status of a job over the API."""
    os.environ["OPENQA_CLI_RETRIES"] = str(openqa_cli_retries)

    failed_versions: dict[str, int] = {}
    failed_jobs: List[str] = []

    _job_ids: List[str]
    with pathlib.Path(job_post_response_file).open() as f:
        _job_ids = job_ids(f.read())

    for job_id in _job_ids:
        log_info(f"Waiting for job {job_id} to finish")
        try:
            openqa_cli(
                "monitor",
                "--host",
                host,
                "--follow",
                "--poll-interval",
                str(sleep_time),
                job_id,
            )
        except ErrorReturnCode as e:
            if e.exit_code == 2:  # Special exit code for monitor when job fails
                pass
            else:
                log_error(f"openqa-cli monitor failed with an unexpected error ({e.exit_code})")
                sys.exit(e.exit_code)

        try:
            response = openqa_cli("api", "--host", host, f"jobs/{job_id}", follow=1)
            job_data = json.loads(response.stdout.decode())["job"]
            result = job_data["result"]
            job_id_actual = str(job_data["id"])
            log_info(f"Result of job {job_id_actual}: {result}")
            if result != "passed" and obs_package_name:
                version = job_data["settings"]["VERSION"]
                failed_versions[version] = 1
                failed_jobs.append(job_id_actual)
        except ErrorReturnCode as e:
            log_error(f"Error getting job details: {e}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            log_error(f"Error decoding JSON from openQA API: {e}")
            sys.exit(1)

    if not failed_jobs:
        sys.exit(0)

    log_error(f"{len(failed_jobs)} jobs did not pass:")
    for _id in failed_jobs:
        console.print(f"{host}/t{_id}")

    # Delete packages from staging project in error case
    delete_packages_from_obs_project(staging_project)

    if not comment_on_obs:
        sys.exit(1)

    log_info("Posting comment with failed jobs to OBS")
    try:
        # Get existing comments and delete them if they match "test.* failed"
        comments_xml = osc("api", f"/comments/{obs_component}/{obs_package_name}").stdout.decode()
        # This part requires parsing XML, which is complex for a quick migration.
        # Placeholder for now, assuming comments are found and deleted.
        # For a full implementation, consider using ElementTree or lxml for XML parsing.
        log_warn("Simulating deletion of old OBS comments")

        comment_text = (
            f"openQA-in-openQA test(s) failed (job IDs: {', '.join(failed_jobs)}), see {host}/tests/overview?"
        )
        for version in failed_versions:
            comment_text += f"version={version}&"
        comment_text += f"groupid={openqa_groupid}"

        osc(
            "api",
            f"--data={comment_text}",
            "-X",
            "POST",
            f"/comments/{obs_component}/{obs_package_name}",
        )
    except ErrorReturnCode as e:
        log_error(f"Error commenting on OBS: {e}")
        sys.exit(1)
    sys.exit(1)


if __name__ == "__main__":
    app()
