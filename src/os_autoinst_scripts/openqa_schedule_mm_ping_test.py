#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script schedules a ping test on openQA by generating a YAML configuration and then using openqa-cli schedule."""

import datetime
import json
import pathlib
import re
import tempfile

import typer
import yaml

from os_autoinst_scripts._common import ErrorReturnCode, log_error, openqa_cli, runcurl

app = typer.Typer()


def download_scenario() -> str:
    scenario_url = (
        f"https://raw.githubusercontent.com/os-autoinst/os-autoinst-distri-openQA/master/{SCENARIO_DEFINITIONS}"
    )
    try:
        response_text = runcurl([scenario_url])
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
            f.write(response_text)
            return f.name
    except Exception as e:
        log_error(f"Error downloading scenario definitions: {e}")
        raise typer.Exit(1)


@app.command()
def main(
    openqa_url: str = typer.Option("https://openqa.opensuse.org", help="openQA URL"),
    distri: str = typer.Option("opensuse", help="Distribution"),
    flavor: str = typer.Option("DVD", help="Flavor"),
    flavor_override: str = typer.Option("mm-monitoring", help="Override flavor"),
    arch: str = typer.Option("x86_64", help="Architecture"),
    version: str = typer.Option("Tumbleweed", help="Version"),
    test_name: str = typer.Option("ping_client", help="Test name"),
    build_regex: str = typer.Option("^[0-9]+$", help="Build regex"),
    machine: str = typer.Option("64bit", help="Machine"),
) -> None:
    """Schedules a ping test on openQA."""
    scenario_definitions = {
        "products": {
            "mm-ping-test": {
                "distri": distri,
                "flavor": flavor_override,
                "arch": arch,
                "version": version,
            }
        },
        "machines": {
            machine: {
                "backend": "qemu",
                "settings": {"WORKER_CLASS": "qemu_x86_64,tap"},
            }
        },
        ".common": {
            "BOOT_HDD_IMAGE": "1",
            "DESKTOP": "textmode",
            "IS_MM_SERVER": "1",
            "NICTYPE": "tap",
            "EXPECTED_NM_CONNECTIVITY": "(limited|full)",
            "QEMU_DISABLE_SNAPSHOTS": "1",
            "YAML_SCHEDULE": "schedule/functional/mm_ping.yaml",
        },
        "job_templates": {
            "ping_server": {
                "product": "mm-ping-test",
                "machine": machine,
                "settings": {"<<": "*common", "HOSTNAME": "server"},
            },
            "ping_client": {
                "product": "mm-ping-test",
                "machine": machine,
                "settings": {"<<": "*common", "HOSTNAME": "client", "PARALLEL_WITH": "ping_server"},
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmpfile:
        yaml.dump(scenario_definitions, tmpfile)
        tmpfile_name = tmpfile.name

    try:
        # Find latest published Tumbleweed image
        response = openqa_cli(
            "api",
            "--host",
            openqa_url,
            "jobs",
            f"version={version}",
            "scope=relevant",
            f"arch={arch}",
            f"machine={machine}",
            f"flavor={flavor}",
            f"test={test_name}",
            "latest=1",
        )
        jobs = json.loads(response.stdout.decode())
        hdd = None
        for job in jobs["jobs"]:
            if job["result"] == "passed" and re.match(build_regex, job["settings"]["BUILD"]):
                if (
                    not hdd or job["settings"]["BUILD"] > job["settings"]["BUILD"]
                ):  # Fixed: hdd should be job["settings"]["HDD_1"]
                    hdd = job["settings"]["HDD_1"]

        if not hdd:
            log_error("Could not find a passed job with HDD_1")
            raise typer.Exit(1)

        build_date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        openqa_cli(
            "schedule",
            "--monitor",
            "--follow",
            "--host",
            openqa_url,
            "--param-file",
            f"SCENARIO_DEFINITIONS_YAML={tmpfile_name}",
            f"DISTRI={distri}",
            f"VERSION={version}",
            f"FLAVOR={flavor_override}",
            f"ARCH={arch}",
            f"BUILD={build_date}",
            "_GROUP_ID=0",
            f"HDD_1={hdd}",
        )
    except ErrorReturnCode as e:
        log_error(f"Error scheduling job: {e.stderr.decode()}")
        raise typer.Exit(1)
    finally:
        pathlib.Path(tmpfile_name).unlink()


if __name__ == "__main__":
    app()
