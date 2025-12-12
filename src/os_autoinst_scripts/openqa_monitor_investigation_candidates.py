#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script queries the openQA database for jobs that are candidates for investigation.
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
    scheme: str = typer.Option("https", help="Scheme to use for the query"),
    interval: str = typer.Option("24 hour", help="Interval to search in"),
    group_id: int = typer.Option(None, help="Limit the search to that job group"),
    exclude_group: str = typer.Option(
        "%Kernel%|%Development%|%Staging%|%MicroOS%",
        help="Exclude all jobs that match the group name specified",
    ),
    exclude_parent: str = typer.Option(
        "%Development|Open Build Service|Others%",
        help="Exclude all jobs that match the parent group name specified",
    ),
    result: str = typer.Option("failed", help="Job result to search for"),
    comment_query: str = typer.Option(
        " and jobs.id not in (select job_id from comments where job_id is not null)",
        help="Additional query for comments",
    ),
    additional_query: str = typer.Option("", help="Optional additional query"),
) -> None:
    """Query the openQA database for jobs that are candidates for investigation.
    """
    if not ssh_host:
        ssh_host = host

    failed_since = f"(timezone('UTC', now()) - interval '{interval}')"
    group_query = f" group_id={group_id} and" if group_id else ""
    exclude_group_query = (
        f" and job_groups.name not similar to '{exclude_group}'" if exclude_group else ""
    )
    exclude_parent_query = (
        f" where job_group_parents.name not similar to '{exclude_parent}'" if exclude_parent else ""
    )
    additional_query = f" and {additional_query}" if additional_query else ""

    query_common_prefix = "select jobs.id,jobs.test, job_groups.parent_id from jobs left join job_groups on jobs.group_id = job_groups.id"
    query_common_suffix = f"result='{result}' and clone_id is null and{group_query} t_finished >= {failed_since}{comment_query}{additional_query}{exclude_group_query}"
    query = f"with included_jobs as ({query_common_prefix} where {query_common_suffix}) select included_jobs.id, test from included_jobs left join job_group_parents on parent_id = job_group_parents.id{exclude_parent_query} union all select included_jobs.id, test from included_jobs where parent_id is null;"

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
