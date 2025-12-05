#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script queries the openQA database for incomplete jobs and prints their URL and details.
"""
import typer
from os_autoinst_scripts._common import console, ErrorReturnCode, ssh

app = typer.Typer()


@app.command()
def main(
    host: str = typer.Option("openqa.opensuse.org", help="openqa host to query"),
    ssh_host: str = typer.Option("", help="SSH host to use for the query"),
    scheme: str = typer.Option("https", help="Scheme to use for the query"),
    interval: str = typer.Option("24 hour", help="Interval to search in"),
) -> None:
    """Query the openQA database for incomplete jobs and print their URL and details.
    """
    if not ssh_host:
        ssh_host = host

    failed_since = f"(timezone('UTC', now()) - interval '{interval}')"
    query = f"select id,test from jobs where (result='incomplete' and (reason is null or (reason not like 'quit%' and reason not like 'abandoned%' and reason not like 'tests died%')) and t_finished >= {failed_since} and id not in (select job_id from comments where job_id is not null) and id not in (select job_id from job_settings where key='CASEDIR'));"

    try:
        output = ssh(
            ssh_host,
            "cd /tmp; sudo -u geekotest psql --no-align --tuples-only --command",
            query,
            "openqa",
        )
        for line in output.stdout.decode().splitlines():
            job_id, details = line.split("|")
            url = f"{scheme}://{host}/tests/{job_id}"
            console.print(f"{url} {details}")
    except Exception as e:
        console.print(f"[bold red]Error querying host {ssh_host}: {e}[/bold red]")


if __name__ == "__main__":
    app()
