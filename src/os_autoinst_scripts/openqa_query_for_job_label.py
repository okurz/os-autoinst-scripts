#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script queries the openQA database for jobs with a specific comment."""

from typing import List

import typer

from os_autoinst_scripts._common import console, ssh

app = typer.Typer()


@app.command()
def main(
    comment: str = typer.Argument(..., help="Comment to search for"),
    host: List[str] = typer.Option(
        ["openqa.opensuse.org", "openqa.suse.de"],
        help="List of hosts to query",
    ),
    scheme: str = typer.Option("https", help="Scheme to use for the query"),
    interval: str = typer.Option("30 day", help="Interval to search in"),
    limit: int = typer.Option(10, help="Limit the number of results"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not do any action on openQA"),
) -> None:
    """Query the openQA database for jobs with a specific comment."""
    failed_since = f"(timezone('UTC', now()) - interval '{interval}')"
    query = f"select jobs.id,t_finished,state,result,test,reason,host from jobs, comments, workers where t_finished >= {failed_since} and jobs.assigned_worker_id = workers.id and jobs.id = comments.job_id and comments.text ~ '{comment}' order by t_finished desc limit {limit};"

    for h in host:
        if dry_run:
            console.print(f"Would ssh to {h} and run query: {query}")
        else:
            try:
                ssh(
                    h,
                    "cd /tmp; sudo -u geekotest psql --no-align --tuples-only --command",
                    query,
                    "openqa",
                )
            except Exception as e:
                console.print(f"[bold red]Error querying host {h}: {e}[/bold red]")


if __name__ == "__main__":
    app()
