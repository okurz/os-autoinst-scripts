#!/usr/bin/env python3
# Copyright SUSE LLC
"""
The script processes GitHub Actions step contexts to generate an HTML summary of failed steps.
"""
import json
import sys
import xml.sax.saxutils
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def main(
    job_name: str = typer.Argument(..., help="Job name"),
    repo_url_arg: str = typer.Argument(..., help="Repository URL (e.g., owner/repo)"),
    run_id: str = typer.Argument(..., help="Run ID"),
    step_context: Optional[str] = typer.Option(None, help="JSON string of step context"),
) -> None:
    """
    Processes GitHub Actions step contexts to generate an HTML summary of failed steps.
    """
    if not step_context:
        typer.echo("::set-output name=result::")
        raise typer.Exit(0)

    try:
        steps = json.loads(step_context)
    except json.JSONDecodeError:
        console.print("[bold red]Error: Invalid JSON for step_context[/bold red]")
        typer.echo("::set-output name=result::")
        raise typer.Exit(1)

    results = ""
    repo_url = f"https://github.com/{repo_url_arg}"
    run_url = f"https://github.com/{repo_url_arg}/actions/runs/{run_id}"

    for k, v in steps.items():
        outcome = v.get("outcome")
        if outcome != "success":
            if not results:
                escaped_repo_url = xml.sax.saxutils.escape(repo_url)
                escaped_repo_arg = xml.sax.saxutils.escape(repo_url_arg)
                results = (
                    f"<p><b>There are failures in the GitHub Actions pipeline for repo"
                    f"<a href='{escaped_repo_url}'>{escaped_repo_arg}</a></b></p>"
                    f"<table><tr><th>Job</th><th>Step</th><th>State</th></tr>"
                )
            
            escaped_pipeline = xml.sax.saxutils.escape(k)
            escaped_outcome = xml.sax.saxutils.escape(outcome)
            escaped_run_url = xml.sax.saxutils.escape(run_url)
            escaped_job_name = xml.sax.saxutils.escape(job_name)

            results += (
                f"<tr><td><a href='{escaped_run_url}'>{escaped_job_name}</td><td>{escaped_pipeline}</td><td>{escaped_outcome}</td></tr>"
            )

    if results:
        results += "</table>"
    else:
        typer.echo("::set-output name=result::")
        raise typer.Exit(0)

    typer.echo(f"::set-output name=result::{results}")
    raise typer.Exit(1) # Original script exits with 1 if there are results

if __name__ == "__main__":
    app()
