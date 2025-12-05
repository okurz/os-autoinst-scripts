#!/usr/bin/env python3
# Copyright SUSE LLC
"""
"hook script" intended to be called by openQA instances taking a job ID as
parameter and forwarding a complete job URL to "openqa-label-known-issues"
on stdin and all left unknowns to "openqa-investigate"
"""
import json
import re
import sys
from typing import Optional

import httpx
import typer
from os_autoinst_scripts._common import console, log_error, runcli, ErrorReturnCode

app = typer.Typer()

HOST = "openqa.opensuse.org"
SCHEME = "https"
HOST_URL = f"{SCHEME}://{HOST}"


def investigate_and_bisect(test_url: str) -> int:
    rc = 0
    try:
        runcli(["openqa-investigate", test_url], check=True)
    except ErrorReturnCode as e:
        rc = e.returncode
    if rc == 142:  # Special exit code for "no bisection needed"
        return rc

    try:
        runcli(["openqa-trigger-bisect-jobs", "-v", "--url", test_url], check=True)
    except ErrorReturnCode as e:
        rc = e.returncode
    return rc


def label(url: str) -> Optional[str]:
    try:
        result = runcli(
            ["openqa-label-known-issues", url], check=True
        )
        match = re.search(r"\[([^]]*)\].*Unknown test issue, to be reviewed.*", result)
        if match:
            return match.group(1)
    except ErrorReturnCode as e:
        log_error(f"Error labeling issue: {e.stderr}")
    return None


@app.command()
def hook(job_id: int = typer.Argument(..., help="Job ID")) -> None:
    """
    Act as a hook for openQA instances, labeling known issues and triggering
    investigations or bisections.
    """
    url = f"{HOST_URL}/tests/{job_id}"
    try:
        response = httpx.get(f"{HOST_URL}/api/v1/jobs/{job_id}")
        response.raise_for_status()
        job_data = response.json()["job"]
    except httpx.HTTPError as e:
        log_error(f"Error fetching job data: {e}")
        # Assuming non-existent job, return silently as per shell script's warn
        return

    state = job_data.get("state")
    result = job_data.get("result")

    if state != "done":
        return

    if result != "passed":
        testsuite = job_data.get("settings", {}).get("TEST", "")
        testsuite = testsuite.replace("container_host_", "")
        testsuite = testsuite.replace("_crun", "")

        if re.match(r"^(aardvark|buildah|conmon|docker|netavark|podman|runc|skopeo)_(e2e|testsuite)$", testsuite):
            try:
                runcli(["openqa-bats-review", url], check=True)
            except ErrorReturnCode as e:
                log_error(f"Error running openqa-bats-review: {e.stderr}")
                raise typer.Exit(e.returncode)
            return

        labeled_issue = label(url)
        if labeled_issue:
            investigate_and_bisect(labeled_issue)
    else:
        investigate_and_bisect(url)


if __name__ == "__main__":
    app()
