#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script searches for jobs in openQA related to a maintenance update.
"""

import httpx
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

DICT_GROUP = {
    "15-SP1": 233,
    "15-SP2": 306,
    "15-SP3": 367,
    "15-SP4": 439,
    "15-SP5": 490,
    "15-SP6": 546,
    "12-SP3": 106,
    "12-SP5": 282,
    "15-SP4-TERADATA": 521,
    "12-SP3-TERADATA": 191,
}

URL_DASHBOARD_QAM = "http://dashboard.qam.suse.de"
URL_OPENQA = "https://openqa.suse.de"
URL_QAM = "https://qam.suse.de"


def rich_print(text: str, color: str) -> None:
    console.print(f"[{color}]{text}[/{color}]")


def search_maintenance_single_incidents(review_request_id: str) -> None:
    rich_print("Maintenance: Single Incidents / Core Incidents", "cyan")
    update_id = review_request_id.split(":")[2]
    incident_settings_url = f"{URL_DASHBOARD_QAM}/api/incident_settings/{update_id}"
    try:
        response = httpx.get(incident_settings_url)
        response.raise_for_status()
        incident_settings = response.json()
    except httpx.HTTPError as e:
        console.print(f"[bold red]Error querying dashboard.qam.suse.de: {e}[/bold red]")
        return

    build = incident_settings[0]["settings"]["BUILD"]
    versions = sorted(list(set(i["settings"]["VERSION"] for i in incident_settings)))
    versions_teradata = sorted(
        list(
            set(
                f'{i["settings"]["VERSION"]}-TERADATA'
                for i in incident_settings
                if "TERADATA" in i["settings"].get("FLAVOR", "")
            )
        )
    )

    for version in versions + versions_teradata:
        groupid = DICT_GROUP.get(version)
        if not groupid:
            continue

        overview_url = f"{URL_OPENQA}/api/v1/jobs/overview?distri=sle&version={version.replace('-TERADATA', '')}&build={build}&groupid={groupid}"
        try:
            response = httpx.get(overview_url)
            response.raise_for_status()
            jobs = response.json()
        except httpx.HTTPError as e:
            console.print(f"[bold red]Error querying openqa: {e}[/bold red]")
            continue

        if not jobs:
            continue

        console.print(f'Version: "{version}" Build: "{build}"')
        console.print(
            f"{URL_OPENQA}/tests/overview?distri=sle&version={version.replace('-TERADATA', '')}&build={build}&groupid={groupid}"
        )

        running_url = f"{overview_url}&state=scheduled&state=running"
        failed_url = f"{overview_url}&result=failed&result=incomplete&result=timeout_exceeded"
        try:
            running_jobs = httpx.get(running_url).json()
            if running_jobs:
                rich_print(f"RUNNING / SCHEDULED ({len(running_jobs)} jobs) Awaiting completion...", "yellow")
                console.print("")
                continue
            failed_jobs = httpx.get(failed_url).json()
            if not failed_jobs:
                rich_print("PASSED", "green")
            else:
                rich_print(f"FAILED ({len(failed_jobs)} jobs)", "red")
            console.print("")
        except httpx.HTTPError as e:
            console.print(f"[bold red]Error querying openqa: {e}[/bold red]")
    console.print("---")


def search_maintenance_aggregated(review_request_id: str, days: int) -> None:
    console.print("Maintenance: Aggregated updates / Core Maintenance Updates", "cyan")
    update_id = review_request_id.split(":")[2]
    groupid = 414
    incident_settings_url = f"{URL_DASHBOARD_QAM}/api/incident_settings/{update_id}"
    try:
        response = httpx.get(incident_settings_url)
        response.raise_for_status()
        versions = sorted(list(set(i["settings"]["VERSION"] for i in response.json())))
    except httpx.HTTPError as e:
        console.print(f"[bold red]Error querying dashboard.qam.suse.de: {e}[/bold red]")
        return

    for version in versions:
        if version not in DICT_GROUP:
            continue

        for day in range(days + 1):
            build = (
                httpx.get(f"https://download.suse.de/ibs/SUSE:/Maintenance:/{update_id}/images/repodata/repomd.xml")
                .text.split("</revision>")[0]
                .split("<revision>")[1]
            )
            overview_url = f"{URL_OPENQA}/api/v1/jobs/overview?distri=sle&version={version}&build={build}&groupid={groupid}&state=done"
            try:
                response = httpx.get(overview_url)
                response.raise_for_status()
                jobs = response.json()
            except httpx.HTTPError as e:
                console.print(f"[bold red]Error querying openqa: {e}[/bold red]")
                continue

            if not jobs:
                continue

            job_id = jobs[0]["id"]
            job_details_url = f"{URL_OPENQA}/api/v1/jobs/{job_id}"
            try:
                response = httpx.get(job_details_url)
                response.raise_for_status()
                job = response.json()["job"]
            except httpx.HTTPError as e:
                console.print(f"[bold red]Error querying openqa: {e}[/bold red]")
                continue

            issues = [
                value
                for key, value in job["settings"].items()
                if "_TEST_ISSUES" in key
            ]
            if update_id in "".join(issues):
                console.print(f"Version: '{version}' Update: '{update_id}'")
                console.print(f"Build {build} contains {update_id}")
                console.print(
                    f"{URL_OPENQA}/tests/overview?distri=sle&version={version}&build={build}&groupid={groupid}"
                )
                running_url = f"{overview_url}&state=scheduled&state=running"
                failed_url = f"{overview_url}&result=failed&result=incomplete&result=timeout_exceeded"
                try:
                    running_jobs = httpx.get(running_url).json()
                    if running_jobs:
                        rich_print(f"RUNNING / SCHEDULED ({len(running_jobs)} jobs) Awaiting completion...", "yellow")
                        console.print("")
                        continue
                    failed_jobs = httpx.get(failed_url).json()
                    if not failed_jobs:
                        rich_print("PASSED", "green")
                    else:
                        rich_print(f"FAILED ({len(failed_jobs)} jobs)", "red")
                    console.print("")
                    break
                except httpx.HTTPError as e:
                    console.print(f"[bold red]Error querying openqa: {e}[/bold red]")
    console.print("---")


def search_build_checks(review_request_id: str) -> None:
    console.print("Build checks", "cyan")
    index_url = f"{URL_QAM}/testreports/{review_request_id}/build_checks"
    try:
        response = httpx.get(index_url)
        response.raise_for_status()
        logs = [
            line.split('href="')[1].split('"')[0]
            for line in response.text.splitlines()
            if 'href="' in line and '.log"' in line
        ]
        if logs:
            console.print(f"Build checks url: {index_url}")
            for log_file in logs:
                log_url = f"{index_url}/{log_file}"
                console.print(f"curl -sLk '{log_url}' | grep ' + exit '")
                log_response = httpx.get(log_url)
                log_response.raise_for_status()
                for line in log_response.text.splitlines():
                    if "+ exit" in line:
                        console.print(line)
                console.print("")
    except httpx.HTTPError as e:
        console.print(f"[bold red]Error querying qam.suse.de: {e}[/bold red]")
    console.print("---")


@app.command()
def main_app(
    review_request_id: str = typer.Argument(..., help="SUSE:Maintenance:II:RR"),
    days: int = typer.Option(5, help="Days to search for aggregated updates"),
) -> None:
    """Search for jobs in openQA related to a maintenance update.
    """
    search_maintenance_single_incidents(review_request_id)
    search_maintenance_aggregated(review_request_id, days)
    search_build_checks(review_request_id)


if __name__ == "__main__":
    main_app()
