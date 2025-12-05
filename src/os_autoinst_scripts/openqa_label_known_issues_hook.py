#!/usr/bin/env python3
# Copyright SUSE LLC
""" "hook script" intended to be called by openQA instances taking a job ID as
parameter and forwarding a complete job URL to "openqa-label-known-issues-multi"
on stdin
"""

import typer

from os_autoinst_scripts._common import ErrorReturnCode, console, runcli

app = typer.Typer()


@app.command()
def main(
    job_id: int = typer.Argument(..., help="Job ID"),
    host: str = typer.Option("openqa.opensuse.org", help="openqa host"),
    scheme: str = typer.Option("https", help="URL scheme"),
) -> None:
    """Take a job ID, construct a URL, and pipe it to openqa-label-known-issues-multi."""
    host_url = f"{scheme}://{host}"
    url = f"{host_url}/tests/{job_id}"
    try:
        runcli(
            ["openqa-label-known-issues-multi"],
            input=url,
            text=True,
            check=True,
        )
    except ErrorReturnCode as e:
        console.print(f"[bold red]Error calling openqa-label-known-issues-multi: {e}[/bold red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
