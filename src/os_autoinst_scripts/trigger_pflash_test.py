#!/usr/bin/env python3
# Copyright SUSE LLC
"""Trigger test to generate pflash vars image."""

import os
import sys

import typer

from os_autoinst_scripts._common import ErrorReturnCode, console, openqa_cli

app = typer.Typer()


def find_latest_published_tumbleweed_image(group_id: int, arch: str, machine: str, image_type: str) -> str:
    # This is a placeholder for the actual implementation
    return "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20240101-Media.iso"


@app.command()
def main(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not do any action on openQA"),
    target_host: str = typer.Option("openqa.opensuse.org", help="Target openQA host"),
    target_host_proto: str = typer.Option("https", help="Target openQA host protocol"),
    tw_openqa_host: str = typer.Option("https://openqa.opensuse.org", help="Tumbleweed openQA host"),
    tw_group_id: int = typer.Option(1, help="Tumbleweed group ID"),
    arch: str = typer.Option("x86_64", help="Architecture"),
    machine: str = typer.Option("64bit", help="Machine"),
    client_prefix: str = typer.Option("", help="Client prefix"),
    openqa_api_key: str = typer.Option(..., envvar="OPENQA_API_KEY", help="openQA API key"),
    openqa_api_secret: str = typer.Option(..., envvar="OPENQA_API_SECRET", help="openQA API secret"),
) -> None:
    """Trigger test to generate pflash vars image."""
    image = find_latest_published_tumbleweed_image(tw_group_id, arch, machine, "iso")

    cli_args: List[str] = []
    triggered_by = os.environ.get("TRIGGERED_BY", sys.argv[0])
    if os.environ.get("GITHUB_SERVER_URL"):
        triggered_by = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/blob/{os.environ['GITHUB_REF_NAME']}/{sys.argv[0]}"
    if triggered_by:
        cli_args.append(f"TRIGGERED_BY={triggered_by}")

    if dry_run:
        console.print("Would trigger test:")
        console.print(
            f"openqa-cli api --host {target_host_proto}://{target_host} -X POST jobs "
            f"--apikey {openqa_api_key} --apisecret {openqa_api_secret} "
            f"TEST=ovmf-resolution@{arch} QEMUVGA=qxl UEFI=1 "
            f"UEFI_PFLASH_CODE=/usr/share/qemu/ovmf-x86_64-ms-code.bin "
            f"UEFI_PFLASH_VARS=/usr/share/qemu/ovmf-x86_64-ms-vars.bin "
            f"PUBLISH_PFLASH_VARS=ovmf-x86_64-ms-vars-800x600.qcow2 "
            f"DISTRI=openSUSE VERSION=Tumbleweed FLAVOR=NET ARCH={arch} "
            f"SCHEDULE=tests/boot/tianocore_set_resolution "
            f"ISO={image} {' '.join(cli_args)}"
        )
    else:
        try:
            openqa_cli(
                "api",
                "--host",
                f"{target_host_proto}://{target_host}",
                "-X",
                "POST",
                "jobs",
                "--apikey",
                openqa_api_key,
                "--apisecret",
                openqa_api_secret,
                f"TEST=ovmf-resolution@{arch}",
                "QEMUVGA=qxl",
                "UEFI=1",
                "UEFI_PFLASH_CODE=/usr/share/qemu/ovmf-x86_64-ms-code.bin",
                "UEFI_PFLASH_VARS=/usr/share/qemu/ovmf-x86_64-ms-vars.bin",
                "PUBLISH_PFLASH_VARS=ovmf-x86_64-ms-vars-800x600.qcow2",
                "DISTRI=openSUSE",
                "VERSION=Tumbleweed",
                "FLAVOR=NET",
                f"ARCH={arch}",
                "SCHEDULE=tests/boot/tianocore_set_resolution",
                f"ISO={image}",
                *cli_args,
            )
        except ErrorReturnCode as e:
            console.print(f"[bold red]Error triggering job: {e.stderr}[/bold red]")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
