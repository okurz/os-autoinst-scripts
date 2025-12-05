#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script uses ripgrep to find the usage of testapi.pm functions in a given repository."""

import pathlib
from typing import List

import typer

from os_autoinst_scripts._common import ErrorReturnCode, console, cut, grep, rg, sort

app = typer.Typer()


def get_function_list(testapi_path: str) -> list[str]:
    try:
        functions = sort(
            grep(
                cut(
                    grep(r"^sub \w+\s*[({:]", testapi_path),
                    "-f2",
                    "-d ",
                ),
                "-v",
                "^_",
            )
        )
        return functions.stdout.decode().splitlines()
    except ErrorReturnCode:
        return []


@app.command()
def main(
    testapi_path: str = typer.Argument(..., help="Path to testapi.pm"),
    repositories: List[str] = typer.Argument(..., help="Path to code repository"),
) -> None:
    """Use ripgrep to find the usage of testapi.pm functions in a given repository."""
    if not testapi_path.endswith("testapi.pm"):
        testapi_path = f"{testapi_path}/testapi.pm"

    try:
        with pathlib.Path(testapi_path).open(encoding="utf-8") as f:
            if "package testapi" not in f.read():
                console.print(
                    "Warning: provided file does not look like testapi.pm",
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
            except ErrorReturnCode:
                console.print(f"{repo} - {function} : 0 matches")


if __name__ == "__main__":
    app()
