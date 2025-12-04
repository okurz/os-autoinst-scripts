#!/usr/bin/env python3
# Copyright SUSE LLC
"""
The script takes a list of openQA test URLs from standard input and calls
label_issue for each of them.
"""
import sys
from typing import List

import typer
from rich.console import Console

from .openqa_label_known_issues import label_issue

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """
    Take a list of openQA test URLs from standard input and call
    label_issue for each of them.
    """
    to_review: List[str] = []
    for line in sys.stdin:
        testurl = line.strip().split(" ")[0]
        try:
            label_issue(testurl)
        except SystemExit:
            to_review.append(testurl)

    if to_review:
        console.print(f"\n[bold red]{len(to_review)} unknown issues to be reviewed:[/bold red]")
        for job in to_review:
            console.print(f" - {job}")


if __name__ == "__main__":
    app()
