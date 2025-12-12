#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script checks for a "Reason for linking:" comment in OBS packages.
"""

import typer
from rich.console import Console
from sh import osc

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Check for a "Reason for linking:" comment in OBS packages.
    """
    osc_cmd = osc.bake("--apiurl", "https://api.opensuse.org")
    problem = False
    projects = osc_cmd.search("--project", "-s", "devel:openQA:Leap:").stdout.decode().splitlines()
    for project in projects:
        project = project.strip()
        if not project.startswith("devel:openQA:Leap:"):
            continue
        packages = osc_cmd.list(project).stdout.decode().splitlines()
        for package in packages:
            package = package.strip()
            try:
                comments = osc_cmd.api(f"/comments/package/{project}/{package}")
                if "Reason for linking:" not in comments.stdout.decode():
                    console.print(
                        f"No reason for {project}/{package}, consider adding a comment or remove the link (see poo#128087 for details)",
                        style="red",
                    )
                    problem = True
            except Exception as e:
                console.print(
                    f"Error checking {project}/{package}: {e}",
                    style="red",
                )
                problem = True
    if problem:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
