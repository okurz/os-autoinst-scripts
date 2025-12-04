#!/usr/bin/env python3
# Copyright SUSE LLC
"""
The script uses ripgrep to find the usage of testapi.pm functions in a given repository.
"""
from typing import List

import typer
from rich.console import Console
from sh import rg, grep, cut, sort

app = typer.Typer()
console = Console()


def get_function_list(testapi_path: str) -> List[str]:
    try:
        functions = sort(
            grep(
                cut(
                    grep("^sub \w+\s*[({:]", testapi_path),
                    "-f2",
                    "-d ",
                ),
                "-v",
                "^_",
            )
        )
        return functions.stdout.decode().splitlines()
    except Exception:
        return []


@app.command()
def main(
    testapi_path: str = typer.Argument(..., help="Path to testapi.pm"),
    repositories: List[str] = typer.Argument(..., help="Path to code repository"),
) -> None:
    """
    Use ripgrep to find the usage of testapi.pm functions in a given repository.
    """
    if not testapi_path.endswith("testapi.pm"):
        testapi_path = f"{testapi_path}/testapi.pm"

    try:
        with open(testapi_path, "r") as f:
            if "package testapi" not in f.read():
                console.print(
                    f"Warning: provided file does not look like testapi.pm",
                    style="yellow",
                )
    except FileNotFoundError:
        console.print(f"{testapi_path} not found", style="red")
        raise typer.Exit(1)

    for repo in repositories:
        for function in get_function_list(testapi_path):
            try:
                usage = rg("--engine", "pcre2", "--stats", f"(?<!_){function}", repo)
                stats = usage.stderr.decode().splitlines()[-1]
                console.print(f"{repo} - {function} : {stats}")
            except Exception:
                console.print(f"{repo} - {function} : 0 matches")


if __name__ == "__main__":
    app()
