#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script checks if the number of "In Progress" tickets in a Redmine query is within a certain limit.
"""

import sys
import httpx
import typer
from os_autoinst_scripts._common import console

app = typer.Typer()


@app.command()
def main(
    redmine_api_key: str = typer.Option(..., help="Redmine API key"),
    host: str = typer.Option("https://progress.opensuse.org", help="Redmine host"),
    query_id: int = typer.Option(400, help="Redmine query ID"),
    ticket_limit: int = typer.Option(200, help="Limit for tickets to fetch"),
    wip_limit: int = typer.Option(10, help="WIP limit"),
    status: str = typer.Option("In Progress", help="Status to check"),
) -> None:
    """Check if the number of "In Progress" tickets in a Redmine query is within a certain limit.
    """
    headers = {"X-Redmine-API-Key": redmine_api_key}
    url = f"{host}/issues.json?query_id={query_id}&limit={ticket_limit}"

    try:
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        issues = response.json()["issues"]
        in_progress_tickets = [
            issue for issue in issues if issue["status"]["name"] == status
        ]

        if len(in_progress_tickets) > wip_limit:
            console.print(
                f"[bold red]WIP limit exceeded: {len(in_progress_tickets)} > {wip_limit}[/bold red]"
            )
            raise typer.Exit(1)
        console.print(
            f"[bold green]WIP limit not exceeded: {len(in_progress_tickets)} <= {wip_limit}[/bold green]"
        )
    except httpx.HTTPError as e:
        console.print(f"[bold red]Error querying Redmine: {e}[/bold red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
