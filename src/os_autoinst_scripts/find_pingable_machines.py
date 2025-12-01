# Copyright (c) 2024 SUSE LLC # noqa: CPY001
import subprocess  # noqa: S404

import requests
import typer
from rich.console import Console

from os_autoinst_scripts.get_unused_machines import get_unused_machines

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    found_machines = 0
    try:
        output = get_unused_machines()
    except requests.RequestException as e:
        console.print(f"Error getting machine list: {e}", style="bold red")
        raise typer.Exit(code=1)  # noqa: B904

    for fqdn in output:
        try:
            result = subprocess.run(
                ["/bin/ping", "-c1", "-W1", fqdn],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                console.print(f"{fqdn} up", style="green")
                found_machines += 1
        except subprocess.SubprocessError as e:
            console.print(f"Error pinging {fqdn}: {e}", style="bold red")

    if found_machines > 0:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
