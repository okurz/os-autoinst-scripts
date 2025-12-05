#!/usr/bin/env python3
# Copyright SUSE LLC
"""
The script cleans up a project on OBS.
"""
import typer
from os_autoinst_scripts._common import console, log_error, log_warn, osc, ErrorReturnCode

app = typer.Typer()


def delete_packages_from_obs_project(obs_project: str) -> None:
    """
    Deletes all packages from an OBS project.
    """
    log_warn(f"Deleting packages from OBS project: {obs_project}")
    try:
        packages = osc("ls", obs_project).stdout.decode().splitlines()
        for package in packages:
            package = package.strip()
            if package:
                log_warn(f"Deleting package {obs_project}/{package}")
                osc("rdelete", "-m", f"Cleaning up {package} from {obs_project}", obs_project, package)
    except ErrorReturnCode as e:
        log_error(f"Error deleting packages from OBS project: {e.stderr}")
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
        log_error("Skipping, pass 'I am sure' as 2nd argument to confirm")
        raise typer.Exit(2)

    delete_packages_from_obs_project(obs_project)


if __name__ == "__main__":
    app()
