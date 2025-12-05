#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script queries openQA for jobs based on various filters and then restarts them."""

from typing import List, Optional

import typer
from rich.console import Console
from sh import openqa_cli, ssh

app = typer.Typer()
console = Console()


@app.command()
def main(
    host: str = typer.Option("openqa.opensuse.org", help="openqa host to query"),
    failed_since: str = typer.Option("", help="Start date for querying failed jobs"),
    instance: Optional[str] = typer.Option(None, help="Instance string"),
    worker: Optional[str] = typer.Option(None, help="Worker host"),
    result: str = typer.Option("result='incomplete'", help="Job result to filter by"),
    additional_filters: Optional[str] = typer.Option(None, help="Additional SQL filters"),
    comment: str = typer.Option("", help="Comment for restarting jobs"),
    max_jobs_per_request: int = typer.Option(25, help="Maximum jobs per restart request"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not perform any actions"),
    job_ids: Optional[List[int]] = typer.Option(None, help="Comma-separated list of job IDs to restart"),
    cli_protocol: Optional[str] = typer.Option(None, help="Protocol for openqa-cli"),
    cli_port: Optional[str] = typer.Option(None, help="Port for openqa-cli"),
) -> None:
    """Queries openQA for jobs based on various filters and then restarts them."""
    if not failed_since:
        import datetime

        failed_since = datetime.date.today().isoformat()

    instance_string = f" and instance='{instance}'" if instance else ""
    worker_string = (
        f"assigned_worker_id in (select id from workers where (host='{worker}'{instance_string})) and "
        if worker
        else ""
    )
    additional_filters_string = f" and {additional_filters}" if additional_filters else ""

    sql_command = f"select id from jobs where ({worker_string}{result} and clone_id is null and t_finished >= '{failed_since}'{additional_filters_string});"

    _job_ids: List[int] = []
    if job_ids:
        _job_ids = job_ids
    else:
        try:
            output = ssh(
                host,
                "sudo -u geekotest psql --no-align --tuples-only --command",
                sql_command,
                "openqa",
            )
            _job_ids = [int(x) for x in output.stdout.decode().splitlines()]
        except Exception as e:
            console.print(f"[bold red]Error querying jobs: {e}[/bold red]")
            raise typer.Exit(1)

    _host = host
    if cli_protocol:
        _host = f"{cli_protocol}://{_host}"
    if cli_port:
        _host = f"{_host}:{cli_port}"

    query_params: List[str] = []

    def restart_jobs():
        if not query_params:
            return
        _query_params = query_params.copy()
        if comment:
            _query_params.append(f"comment={comment}")
        if dry_run:
            console.print(f"Would restart jobs: {', '.join(_query_params)}")
        else:
            try:
                openqa_cli(
                    "api",
                    "--host",
                    _host,
                    "-X",
                    "POST",
                    "jobs/restart",
                    *_query_params,
                )
            except Exception as e:
                console.print(f"[bold red]Error restarting jobs: {e}[/bold red]")
        query_params.clear()

    for job_id in _job_ids:
        query_params.append(f"jobs={job_id}")
        if len(query_params) >= max_jobs_per_request:
            restart_jobs()
    restart_jobs()


if __name__ == "__main__":
    app()
