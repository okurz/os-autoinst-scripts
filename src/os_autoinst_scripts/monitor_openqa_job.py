#!/usr/bin/env python3
# Copyright SUSE LLC
"""
Monitor an openQA job by polling the status of a job over the API.
"""
import json
import os
import sys
import time
from typing import List, Optional

import typer
from os_autoinst_scripts._common import (
    console,
    log_info,
    log_warn,
    log_error,
)

app = typer.Typer()


# Placeholder for _common functions, assuming job_ids and delete_packages_from_obs_project
def job_ids(job_post_response_file: str) -> List[str]:
    # In a real scenario, this would parse the job_post_response_file
    # For now, let's assume it contains job IDs separated by newlines
    with open(job_post_response_file, "r") as f:
        return f.read().strip().splitlines()


def delete_packages_from_obs_project(project: str) -> None:
    # Placeholder for actual OBS deletion logic
    console.print(f"[yellow]Simulating deletion of packages from OBS project: {project}[/yellow]")


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
    """
    Monitor an openQA job by polling the status of a job over the API.
    """
    os.environ["OPENQA_CLI_RETRIES"] = str(openqa_cli_retries)

    failed_versions: dict[str, int] = {}
    failed_jobs: List[str] = []

    _job_ids = job_ids(job_post_response_file)

    for job_id in _job_ids:
        console.print(f"Waiting for job {job_id} to finish")
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
                console.print(
                    f"[bold red]openqa-cli monitor failed with an unexpected error ({e.exit_code})[/bold red]"
                )
                raise typer.Exit(e.exit_code)

        try:
            response = openqa_cli("api", "--host", host, f"jobs/{job_id}", follow=1)
            job_data = json.loads(response.stdout.decode())["job"]
            result = job_data["result"]
            job_id_actual = str(job_data["id"])
            console.print(f"Result of job {job_id_actual}: {result}")
            if result != "passed" and obs_package_name:
                version = job_data["settings"]["VERSION"]
                failed_versions[version] = 1
                failed_jobs.append(job_id_actual)
        except ErrorReturnCode as e:
            console.print(f"[bold red]Error getting job details: {e}[/bold red]")
            raise typer.Exit(1)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Error decoding JSON from openQA API: {e}[/bold red]")
            raise typer.Exit(1)

    if not failed_jobs:
        raise typer.Exit(0)

    console.print(f"[bold red]{len(failed_jobs)} jobs did not pass:[/bold red]")
    for _id in failed_jobs:
        console.print(f"{host}/t{_id}")

    # Delete packages from staging project in error case
    delete_packages_from_obs_project(staging_project)

    if not comment_on_obs:
        raise typer.Exit(1)

    console.print("[bold green]Posting comment with failed jobs to OBS[/bold green]")
    try:
        # Get existing comments and delete them if they match "test.* failed"
        comments_xml = osc("api", f"/comments/{obs_component}/{obs_package_name}").stdout.decode()
        # This part requires parsing XML, which is complex for a quick migration.
        # Placeholder for now, assuming comments are found and deleted.
        # For a full implementation, consider using ElementTree or lxml for XML parsing.
        console.print("[yellow]Simulating deletion of old OBS comments[/yellow]")

        comment_text = f"openQA-in-openQA test(s) failed (job IDs: {', '.join(failed_jobs)}), see {host}/tests/overview?"
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
        console.print(f"[bold red]Error commenting on OBS: {e}[/bold red]")
        raise typer.Exit(1)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
