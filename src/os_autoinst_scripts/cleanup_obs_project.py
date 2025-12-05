#!/usr/bin/env python3
# Copyright SUSE LLC
"""
The script cleans up a project on OBS.
"""
import typer
from rich.console import Console
from sh import osc, ErrorReturnCode

app = typer.Typer()
console = Console()


def delete_packages_from_obs_project(obs_project: str) -> None:
    """
    Deletes all packages from an OBS project.
    """
    console.print(f"[yellow]Deleting packages from OBS project: {obs_project}[/yellow]")
    try:
        packages = osc("ls", obs_project).stdout.decode().splitlines()
        for package in packages:
            package = package.strip()
            if package:
                console.print(f"[yellow]Deleting package {obs_project}/{package}[/yellow]")
                osc("rdelete", "-m", f"Cleaning up {package} from {obs_project}", obs_project, package)
    except ErrorReturnCode as e:
        console.print(f"[bold red]Error deleting packages from OBS project: {e.stderr}[/bold red]")
        raise typer.Exit(1)


@app.command()
def main(
    obs_project: str = typer.Argument(..., help="OBS project to clean up"),
    confirmation: str = typer.Argument(..., help="Confirmation phrase ('I am sure')"),
) -> None:
    """
    Cleans up a project on OBS.
    """
    if confirmation != "I am sure":
        console.print("[bold red]Skipping, pass 'I am sure' as 2nd argument to confirm[/bold red]")
        raise typer.Exit(2)

    delete_packages_from_obs_project(obs_project)


if __name__ == "__main__":
    app()
