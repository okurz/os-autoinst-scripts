#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script calls openqa-investigate for each job ID provided on standard input."""

import sys

import typer

from os_autoinst_scripts._common import ErrorReturnCode, runcli

app = typer.Typer()


@app.command()
def main() -> None:
    """Call openqa-investigate for each job ID provided on standard input."""
    rc = 0
    for line in sys.stdin:
        job_id = line.strip().split(" ")[0]
        try:
            runcli(["openqa-investigate", job_id])
        except ErrorReturnCode as e:
            rc = e.returncode

    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
