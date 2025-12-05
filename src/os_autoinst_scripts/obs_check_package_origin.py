#!/usr/bin/env python3
# Copyright SUSE LLC
"""
The script checks the origin of packages and their versions in OBS and Tumbleweed.
"""
import sys
from typing import List

import typer
from os_autoinst_scripts._common import (
    basename,
    console,
    cut,
    ErrorReturnCode,
    grep,
    osc,
    rpmspec,
    sed,
    sort,
    tr,
    zypper,
)

app = typer.Typer()
osc_cmd = osc.bake("--apiurl", "https://api.opensuse.org")


def get_package_version(package: str) -> str:
    try:
        spec_file = f"{basename(package)}.spec"
        spec_content = osc_cmd.cat(package, spec_file)
        version = rpmspec("-q", "--qf", "%{{version}}\n", _in=spec_content).stdout.decode().strip()
        return version.splitlines()[0]
    except ErrorReturnCode:
        return "-"


def get_tw_version(package: str) -> str:
    try:
        output = zypper("-n", "--no-refresh", "info", package).stdout.decode()
        for line in output.splitlines():
            if line.startswith("Version"):
                return line.split(":")[1].strip()
    except ErrorReturnCode:
        pass
    return "-"

def get_package_name(req: str) -> str:
    try:
        package = req.split(" ")[0]
        output = osc_cmd.se("--package", package).stdout.decode()
        return output.split("'")[1]
    except (ErrorReturnCode, IndexError):
        return ""

def list_requirements(package: str) -> List[str]:
    try:
        spec_content = osc_cmd.cat("devel:openQA", package, f"_service:obs_scm:{package}.spec")
        spec_content = sed(
            "-e", "/node_modules.spec.inc/d", _in=spec_content
        ).stdout.decode()
        build_requires = rpmspec(
            "-q",
            "-D",
            "sysusers_requires BuildRequires: sysuser-tools",
            "--buildrequires",
            _in=spec_content,
        ).stdout.decode()
        requires = rpmspec(
            "-q",
            "-D",
            "sysusers_requires BuildRequires: sysuser-tools",
            "--requires",
            _in=spec_content,
        ).stdout.decode()
        reqs = sorted(list(set(build_requires.splitlines() + requires.splitlines())))
        packages = []
        for req in reqs:
            pkg = get_package_name(req)
            if pkg:
                packages.append(pkg)
        return packages
    except ErrorReturnCode:
        return []

def get_codestream(package: str) -> str:
    try:
        return osc_cmd.sm(package, _err_to_out=True).stdout.decode().split(" ")[0]
    except ErrorReturnCode:
        return ""

def find_source_package(package: str) -> str:
    try:
        info_output = zypper("-n", "--no-refresh", "info", package).stdout.decode()
        for line in info_output.splitlines():
            if "Source package" in line:
                source_package = line.split(":")[1].strip()
                search_output = zypper(
                    "-n", "--no-refresh", "--xmlout", "se", "-t", "srcpackage", source_package
                ).stdout.decode()
                return grep(
                    "-oP", "'[^']+'", _in=search_output
                ).stdout.decode().strip().replace("'", "")
    except (ErrorReturnCode, IndexError):
        pass
    return ""

def search_provides(req: str) -> List[str]:
    try:
        provides_output = zypper(
            "-n", "--no-refresh", "--xmlout", "se", "--provides", req
        ).stdout.decode()
        provides = grep(
            "-oP", "'[^']+'", _in=provides_output
        ).stdout.decode().strip().replace("'", "").splitlines()
        console.print(f"{req} is provided by {provides}")
        source_packages = []
        for prov in provides:
            src = find_source_package(prov)
            if src:
                source_packages.append(src)
        return [get_codestream(src) for src in sorted(list(set(source_packages)))]
    except ErrorReturnCode:
        return []

def list_versions(package: str) -> None:
    codestreams = []
    for req in list_requirements(package):
        stream = get_codestream(req)
        if stream:
            codestreams.append(stream)
        else:
            codestreams.extend(search_provides(req))
    codestreams = sorted(list(set(codestreams)))
    for stream in codestreams:
        version = get_package_version(stream)
        tw_version = get_tw_version(stream)
        console.print(f"{stream}\t{version}\t{tw_version}")


@app.command()
def main(packages: List[str] = typer.Argument(..., help="Package name(s)")) -> None:
    """
    Check the origin of packages and their versions in OBS and Tumbleweed.
    """
    for package in packages:
        list_versions(package)


if __name__ == "__main__":
    app()
