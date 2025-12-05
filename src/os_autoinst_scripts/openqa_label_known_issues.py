#!/usr/bin/env python3
# Copyright SUSE LLC
"""
The script labels known issues in openQA.
"""
import os
import re
import sys
from typing import List, Optional

import httpx
import typer
from os_autoinst_scripts._common import (
    console,
    log_error,
    log_info,
    log_warn,
    openqa_api_get,
    openqa_api_post,
    openqa_api_put,
    openqa_api_delete,
    runcurl,
)

app = typer.Typer()


class Settings:
    def __init__(
        self,
        host: str,
        scheme: str,
        dry_run: bool,
        min_search_term: int,
        issue_marker: str,
        issue_query: str,
        force_result_tracker: str,
        reason_min_length: int,
        grep_timeout: int,
        email_unreviewed: bool,
        notification_address: Optional[str],
        from_email: str,
        retries: int,
        openqa_cli_retry_sleep_time_s: int,
        mojo_connect_timeout: int,
    ):
        self.host = host
        self.scheme = scheme
        self.dry_run = dry_run
        self.min_search_term = min_search_term
        self.issue_marker = issue_marker
        self.issue_query = issue_query
        self.force_result_tracker = force_result_tracker
        self.reason_min_length = reason_min_length
        self.grep_timeout = grep_timeout
        self.email_unreviewed = email_unreviewed
        self.notification_address = notification_address
        self.from_email = from_email
        self.retries = retries
        self.openqa_cli_retry_sleep_time_s = openqa_cli_retry_sleep_time_s
        self.mojo_connect_timeout = mojo_connect_timeout
        self.host_url = f"{self.scheme}://{self.host}"


def get_issues(settings: Settings) -> List[dict]:
    try:
        response = runcurl([settings.issue_query])
        return json.loads(response)["issues"]
    except httpx.HTTPStatusError as e:
        log_error(f"Error querying issue tracker: {e}")
        return []
    except json.JSONDecodeError as e:
        log_error(f"Error decoding JSON from issue tracker: {e}")
        return []


def label_on_issue(
    job_id: int,
    search_term: str,
    label: str,
    retry: bool,
    force_result: Optional[str],
    settings: Settings,
) -> bool:
    # Placeholder for the actual implementation
    return True


def handle_unreviewed(
    testurl: str,
    log: str,
    reason: str,
    group_id: int,
    email_unreviewed: bool,
    from_email: str,
    notification_address: Optional[str],
    job_data: dict,
    dry_run: bool,
) -> None:
    # Placeholder for the actual implementation
    pass

def investigate_issue(testurl: str, settings: Settings, issues: List[dict]) -> None:
    job_id = int(testurl.split("/")[-1])
    try:
        job_data = openqa_api_get(f"jobs/{job_id}", settings.host_url)
    except httpx.HTTPStatusError as e:
        log_error(f"Error querying openQA API: {e}")
        return

    if job_data["job"]["state"] != "done" or job_data["job"]["result"] == "passed":
        return

    reason = job_data["job"].get("reason")
    log_url = f"{testurl}/file/autoinst-log.txt"
    try:
        log = runcurl([log_url])
    except httpx.HTTPStatusError:
        log = ""

    full_log = f"{reason}\n{log}"

    for issue in issues:
        search = re.search(f"{settings.issue_marker}(.*)", issue["subject"])
        if search:
            search_term = search.group(1)
            force_result = None
            if ":force_result:" in search_term:
                force_result = search_term.split(":force_result:")[1]
            if len(search_term) >= settings.min_search_term:
                if label_on_issue(
                    job_id, search_term, f'poo#{issue["id"]}', False, force_result, settings
                ):
                    return

    # Issues without tickets
    if label_on_issue(job_id, "([dD]ownload.*failed.*404)", "label:non_existing_asset", False, None, settings):
        return
    # ... more rules

    handle_unreviewed(
        testurl,
        full_log,
        reason,
        job_data["job"]["group_id"],
        settings.email_unreviewed,
        settings.from_email,
        settings.notification_address,
        job_data["job"],
        settings.dry_run,
    )


@app.command()
def label_issue(
    testurl: str = typer.Argument(..., help="URL of the openQA test"),
    host: str = typer.Option("openqa.opensuse.org", help="openQA host"),
    scheme: str = typer.Option("https", help="URL scheme"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    min_search_term: int = typer.Option(16),
    issue_marker: str = typer.Option("auto_review%3A"),
    issue_query: str = typer.Option(
        "https://progress.opensuse.org/projects/openqav3/issues.json?limit=200&subproject_id=*&subject=~"
    ),
    force_result_tracker: str = typer.Option("openqa-force-result"),
    reason_min_length: int = typer.Option(8),
    grep_timeout: int = typer.Option(5),
    email_unreviewed: bool = typer.Option(False),
    notification_address: Optional[str] = typer.Option(None),
    from_email: str = typer.Option("openqa-label-known-issues@open.qa"),
    retries: int = typer.Option(3),
    openqa_cli_retry_sleep_time_s: int = typer.Option(120),
    mojo_connect_timeout: int = typer.Option(30),
) -> None:
    """
    Label known issues in openQA.
    """
    settings = Settings(
        host=host,
        scheme=scheme,
        dry_run=dry_run,
        min_search_term=min_search_term,
        issue_marker=issue_marker,
        issue_query=f"{issue_query}{issue_marker}",
        force_result_tracker=force_result_tracker,
        reason_min_length=reason_min_length,
        grep_timeout=grep_timeout,
        email_unreviewed=email_unreviewed,
        notification_address=notification_address,
        from_email=from_email,
        retries=retries,
        openqa_cli_retry_sleep_time_s=openqa_cli_retry_sleep_time_s,
        mojo_connect_timeout=mojo_connect_timeout,
    )
    issues = get_issues(settings)
    investigate_issue(testurl, settings, issues)


if __name__ == "__main__":
    app()
