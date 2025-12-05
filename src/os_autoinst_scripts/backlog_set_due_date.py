#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script sets the due date on tickets in Redmine based on specified conditions."""

import datetime
import pathlib
from typing import Optional

import httpx
import typer
from rich.console import Console

app = typer.Typer()
console = Console()


class Settings:
    def __init__(
        self,
        redmine_api_key: str,
        host: str,
        query_id: int,
        ticket_limit: int,
        status: str,
        duration: str,
        priority: str,
        dry_run: bool,
        issues_file: Optional[str],
    ):
        self.redmine_api_key = redmine_api_key
        self.host = host
        self.query_id = query_id
        self.ticket_limit = ticket_limit
        self.status = status
        self.duration = duration
        self.priority = priority
        self.dry_run = dry_run
        self.issues_file = issues_file


@app.callback()
def callback(
    ctx: typer.Context,
    redmine_api_key: str = typer.Option(..., help="Redmine API key", envvar="REDMINE_API_KEY"),
    host: str = typer.Option("https://progress.opensuse.org", help="Redmine host"),
    query_id: int = typer.Option(230, help="Redmine query ID"),
    ticket_limit: int = typer.Option(200, help="Limit for tickets to fetch"),
    status: str = typer.Option("In Progress", help="Status to check"),
    duration: str = typer.Option("14 days", help="Duration to add to the current date"),
    priority: str = typer.Option("Low", help="Priority to exclude"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not do any action on Redmine"),
    issues_file: Optional[str] = typer.Option(None, help="Read issues from a file instead of Redmine"),
) -> None:
    """Set the due date on tickets in Redmine based on specified conditions."""
    ctx.meta["settings"] = Settings(
        redmine_api_key,
        host,
        query_id,
        ticket_limit,
        status,
        duration,
        priority,
        dry_run,
        issues_file,
    )


@app.command()
def main(ctx: typer.Context) -> None:
    settings: Settings = ctx.meta["settings"]
    headers = {"X-Redmine-API-Key": settings.redmine_api_key}
    if settings.issues_file and settings.dry_run:
        with pathlib.Path(settings.issues_file).open("r", encoding="utf-8") as f:
            issues = f.read()
    else:
        url = f"{settings.host}/issues.json?query_id={settings.query_id}&limit={settings.ticket_limit}"
        try:
            response = httpx.get(url, headers=headers)
            response.raise_for_status()
            issues = response.json()["issues"]
        except httpx.HTTPError as e:
            console.print(f"[bold red]Error querying Redmine: {e}[/bold red]")
            raise typer.Exit(1)

    due_date = (datetime.date.today() + datetime.timedelta(days=int(settings.duration.split(maxsplit=1)[0]))).strftime(
        "%Y-%m-%d"
    )

    for issue in issues:
        if (
            issue["priority"]["name"] != settings.priority
            and issue.get("due_date") is None
            and issue.get("assigned_to") is not None
            and issue["status"]["name"] == settings.status
        ):
            console.print(f"Updating ticket {issue['id']}, new due date setup to {due_date}")
            if not settings.dry_run:
                url = f"{settings.host}/issues/{issue['id']}.json"
                data = {
                    "issue": {
                        "due_date": due_date,
                        "notes": "Setting due date based on mean cycle time of SUSE QE Tools",
                    }
                }
                try:
                    response = httpx.put(url, headers=headers, json=data)
                    response.raise_for_status()
                except httpx.HTTPError as e:
                    console.print(f"[bold red]Error updating ticket {issue['id']}: {e}[/bold red]")


if __name__ == "__main__":
    app()
