#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script calls openqa-investigate for each job ID provided on standard input.
"""
import subprocess
import sys

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Call openqa-investigate for each job ID provided on standard input.
    """
    rc = 0
    for line in sys.stdin:
        job_id = line.strip().split(" ")[0]
        try:
            subprocess.run(["openqa-investigate", job_id], check=True)
        except subprocess.CalledProcessError as e:
            rc = e.returncode

    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
