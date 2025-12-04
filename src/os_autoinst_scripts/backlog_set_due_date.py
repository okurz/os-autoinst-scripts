#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script sets the due date on tickets in Redmine based on specified conditions."""
import datetime
import pathlib

import httpx
import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def main(
    redmine_api_key: str = typer.Option(..., help="Redmine API key"),
    host: str = typer.Option("https://progress.opensuse.org", help="Redmine host"),
    query_id: int = typer.Option(230, help="Redmine query ID"),
    ticket_limit: int = typer.Option(200, help="Limit for tickets to fetch"),
    status: str = typer.Option("In Progress", help="Status to check"),
    duration: str = typer.Option("14 days", help="Duration to add to the current date"),
    priority: str = typer.Option("Low", help="Priority to exclude"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not do any action on Redmine"),
    issues_file: str = typer.Option(None, help="Read issues from a file instead of Redmine"),
) -> None:
    """Set the due date on tickets in Redmine based on specified conditions.
    """
    headers = {"X-Redmine-API-Key": redmine_api_key}
    if issues_file and dry_run:
        with pathlib.Path(issues_file).open("r", encoding="utf-8") as f:
            issues = f.read()
    else:
        url = f"{host}/issues.json?query_id={query_id}&limit={ticket_limit}"
        try:
            response = httpx.get(url, headers=headers)
            response.raise_for_status()
            issues = response.json()["issues"]
        except httpx.HTTPError as e:
            console.print(f"[bold red]Error querying Redmine: {e}[/bold red]")
            raise typer.Exit(1)

    due_date = (datetime.date.today() + datetime.timedelta(days=int(duration.split(maxsplit=1)[0]))).strftime("%Y-%m-%d")

    for issue in issues:
        if (
            issue["priority"]["name"] != priority
            and issue.get("due_date") is None
            and issue.get("assigned_to") is not None
            and issue["status"]["name"] == status
        ):
            console.print(f"Updating ticket {issue['id']}, new due date setup to {due_date}")
            if not dry_run:
                url = f"{host}/issues/{issue['id']}.json"
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
                    console.print(
                        f"[bold red]Error updating ticket {issue['id']}: {e}[/bold red]"
                    )


if __name__ == "__main__":
    app()
