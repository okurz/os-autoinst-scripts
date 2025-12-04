#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script queries the openQA database for statistics about incomplete jobs.
"""

import typer
from rich.console import Console
from sh import ssh

app = typer.Typer()
console = Console()


@app.command()
def main(
    host: str = typer.Option("openqa.opensuse.org", help="openqa host to query"),
    ssh_host: str = typer.Option("", help="SSH host to use for the query"),
    interval: str = typer.Option("24 hour", help="Interval to search in"),
    width: int = typer.Option(80, help="Width of the comment text"),
    threshold: int = typer.Option(0, help="Threshold for the number of jobs"),
    show_job_ids: bool = typer.Option(False, "--show-job-ids", help="Show job IDs"),
    show_worker_hosts: bool = typer.Option(
        False, "--show-worker-hosts", help="Show worker hosts"
    ),
) -> None:
    """Query the openQA database for statistics about incomplete jobs.
    """
    if not ssh_host:
        ssh_host = host

    failed_since = f"(timezone('UTC', now()) - interval '{interval}')"
    additional_columns = ""
    if show_job_ids:
        additional_columns += ", array_agg(jobs.id) as job_ids"
    if show_worker_hosts:
        additional_columns += ", array(select distinct host from workers where id = any(array_agg(jobs.assigned_worker_id))) as worker_hosts"

    query = f"select left(text, {width}) as comment_text, count(text) as job_count {additional_columns} from jobs join comments on jobs.id = comments.job_id where result='incomplete' and t_finished >= {failed_since} group by text having count(text) > {threshold} order by job_count desc;"

    try:
        ssh(
            ssh_host,
            "cd /tmp; sudo -u geekotest psql --command",
            query,
            "openqa",
        )
    except Exception as e:
        console.print(f"[bold red]Error querying host {ssh_host}: {e}[/bold red]")


if __name__ == "__main__":
    app()
