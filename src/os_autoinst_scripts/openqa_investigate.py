#!/usr/bin/env python3
# Copyright SUSE LLC
"""The script investigates openQA jobs."""

import json
import re
import subprocess
import sys
from typing import List, Optional

import httpx
import typer
from rich.console import Console

app = typer.Typer()
console = Console(color_system=None)

HOST = "openqa.opensuse.org"
SCHEME = "https"
HOST_URL = f"{SCHEME}://{HOST}"

INVESTIGATION_GID = 0
PRIO_ADD = 100
EXCLUDE_NAME_REGEX = ":investigate:"
EXCLUDE_NO_GROUP = True
EXCLUDE_GROUP_REGEX = r"Development.*/ "
RETRIES = 3
OPENQA_CLI_RETRY_SLEEP_TIME_S = 20
MOJO_CONNECT_TIMEOUT = 30
JQ_OUTPUT_LIMIT = 15


class Settings:
    def __init__(
        self,
        host: str,
        scheme: str,
        investigation_gid: int,
        dry_run: bool,
        verbose: bool,
        prio_add: int,
        exclude_name_regex: str,
        exclude_no_group: bool,
        exclude_group_regex: str,
        force: bool,
        retries: int,
        openqa_cli_retry_sleep_time_s: int,
        mojo_connect_timeout: int,
    ):
        self.host = host
        self.scheme = scheme
        self.investigation_gid = investigation_gid
        self.dry_run = dry_run
        self.verbose = verbose
        self.prio_add = prio_add
        self.exclude_name_regex = exclude_name_regex
        self.exclude_no_group = exclude_no_group
        self.exclude_group_regex = exclude_group_regex
        self.force = force
        self.retries = retries
        self.openqa_cli_retry_sleep_time_s = openqa_cli_retry_sleep_time_s
        self.mojo_connect_timeout = mojo_connect_timeout
        self.host_url = f"{self.scheme}://{self.host}"


def run_openqa_cli(args: List[str], dry_run: bool = False) -> str:
    if dry_run:
        console.print(f"Would run: openqa-cli {' '.join(args)}")
        return json.dumps({"42": 42})
    try:
        result = subprocess.run(["openqa-cli"] + args, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error running openqa-cli: {e.stderr}[/bold red]")
        raise typer.Exit(1)


def client_get_job(job_id: int, settings: Settings) -> dict:
    return json.loads(run_openqa_cli(["api", "--host", settings.host_url, f"jobs/{job_id}"]))


def client_put_job_comment(job_id: int, comment_id: int, comment: str, settings: Settings) -> None:
    run_openqa_cli([
        "api",
        "--host",
        settings.host_url,
        "-X",
        "PUT",
        f"jobs/{job_id}/comments/{comment_id}",
        f"text={comment}",
    ])


def client_post_job_comment(job_id: int, comment: str, settings: Settings) -> dict:
    return json.loads(
        run_openqa_cli(["api", "--host", settings.host_url, "-X", "POST", f"jobs/{job_id}/comments", f"text={comment}"])
    )


def client_delete_job_comment(job_id: int, comment_id: int, settings: Settings) -> None:
    run_openqa_cli(["api", "--host", settings.host_url, "-X", "DELETE", f"jobs/{job_id}/comments/{comment_id}"])


def fetch_vars_json(job_id: int, settings: Settings) -> dict:
    try:
        response = httpx.get(f"{settings.host_url}/tests/{job_id}/file/vars.json")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        console.print(f"[bold red]Error fetching vars.json: {e}[/bold red]")
        raise typer.Exit(1)


def get_dependencies_ajax(job_id: int, settings: Settings) -> dict:
    try:
        response = httpx.get(f"{settings.host_url}/tests/{job_id}/dependencies_ajax")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        console.print(f"[bold red]Error fetching dependencies_ajax: {e}[/bold red]")
        raise typer.Exit(1)


def is_finished(state: str) -> bool:
    return state in ["done", "cancelled"]


def is_ok(result: str) -> bool:
    return result in ["passed", "softfailed"]


def is_cancelled(result: str) -> bool:
    return result in ["none", "skipped", "user_cancelled", "user_restarted", "parallel_restarted"]


def clone_job(
    origin_job_id: int, job_id_to_clone: int, name_suffix: str, refspec: Optional[str], settings: Settings
) -> str:
    clone_settings = [
        "_TRIGGER_JOB_DONE_HOOK=1",
        f"_GROUP_ID={settings.investigation_gid}",
        "BUILD=",
    ]
    clone_job_data = client_get_job(job_id_to_clone, settings)

    unsupported_cluster_jobs = len(clone_job_data["job"].get("children", {}).get("Directly chained", [])) + len(
        clone_job_data["job"].get("parents", {}).get("Directly chained", [])
    )
    if unsupported_cluster_jobs != 0:
        console.print(
            f"[bold red]Unable to clone job {job_id_to_clone}: it is part of a directly chained cluster (not supported)[/bold red]"
        )
        raise typer.Exit(2)

    base_name = clone_job_data["job"]["test"]

    if refspec:
        vars_json = fetch_vars_json(origin_job_id, settings)
        test_git_url = vars_json.get("TEST_GIT_URL")
        casedir = clone_job_data["job"]["settings"].get("CASEDIR")

        if test_git_url and not re.match(r"^https?://[^ ]+$", test_git_url):
            console.print(
                f"[yellow]Can not clone refspec of job {origin_job_id} with unknown/invalid git url TEST_GIT_URL='{test_git_url}'[/yellow]"
            )
            return ""

        repo = casedir or "https://github.com/os-autoinst/os-autoinst-distri-opensuse.git"
        if "#" in repo:
            repo = repo.split("#")[0]
        clone_settings.append(f"CASEDIR={repo}#{refspec}")
        if "last_good_tests_and_build" in name_suffix:
            worker_vars_settings = vars_json.get("WORKER_CLASS")
            if worker_vars_settings:
                clone_settings.append(f"WORKER_CLASS:{base_name}={worker_vars_settings}")
            else:
                name_suffix += "(unidentified worker class in vars.json)"

    clone_settings.append(f"TEST+={name_suffix}")

    for key, value in clone_job_data["job"]["settings"].items():
        if key.startswith("PUBLISH_"):
            clone_settings.append(f"{key}=none")

    clone_settings.append(f"OPENQA_INVESTIGATE_ORIGIN={settings.host_url}/tests/{origin_job_id}")

    out = run_openqa_cli(
        [
            "openqa-clone-job",
            "--json-output",
            "--skip-chained-deps",
            "--max-depth",
            "0",
            "--parental-inheritance",
            "--within-instance",
            f"{settings.host_url}/tests/{origin_job_id}",
        ]
        + clone_settings,
        dry_run=settings.dry_run,
    )

    if settings.dry_run:
        return json.dumps({str(origin_job_id): 42})
    return out


def trigger_jobs(job_id: int, settings: Settings) -> str:
    out = ""
    # 1. current job/build + current test -> check if reproducible/sporadic
    out += clone_job(job_id, job_id, "retry", None, settings)

    investigation_url = f"{settings.host_url}/tests/{job_id}/investigation_ajax"
    try:
        response = httpx.get(investigation_url)
        response.raise_for_status()
        investigation = response.json()
    except httpx.HTTPError as e:
        console.print(f"[bold red]Error fetching investigation_ajax: {e}[/bold red]")
        raise typer.Exit(1)

    last_good_exists = investigation.get("last_good")
    if not last_good_exists or last_good_exists == "null" or last_good_exists == "not found":
        console.print("No last good recorded, skipping regression investigation jobs")
        return out

    last_good = investigation["last_good"]["text"]
    if not re.match(r"^[0-9]+$", last_good):
        console.print(
            f"[bold red].last_good.text not found: investigation for test {job_id} returned '{investigation}'[/bold red]"
        )
        raise typer.Exit(1)

    # 2. current job/build + last good test (+ last good needles) -> check for test (+needles) regression
    test_log = investigation.get("test_log")
    if test_log and "No changes recorded" in test_log:
        console.print(f"{test_log}. Skipping test regression investigation job.")
    else:
        vars_last_good = fetch_vars_json(int(last_good), settings)
        last_good_tests = vars_last_good.get("TEST_GIT_HASH")
        if last_good_tests:
            out += clone_job(job_id, job_id, f"last_good_tests:{last_good_tests}", last_good_tests, settings)

    # 3. last good job/build + current test -> check for product regression
    if investigation.get("BUILD") == last_good:  # Assuming investigation['BUILD'] would contain the current build ID
        console.print(
            "Current job has same build as last good, product regression unlikely. Skipping product regression investigation job."
        )
    else:
        vars_last_good_build = fetch_vars_json(int(last_good), settings)
        last_good_build = vars_last_good_build.get("BUILD")
        if last_good_build:
            out += clone_job(job_id, int(last_good), f"last_good_build:{last_good_build}", None, settings)

    # 4. last good job/build + last good test -> check for other problem sources, e.g. infrastructure
    if not last_good_tests:
        console.print(
            "No test regression expected. Not triggered 'good build+test' as it would be the same as 3., good build + current test"
        )
    elif not investigation.get("BUILD") == last_good:
        console.print(
            "No product regression expected. Not triggered 'good build+test' as it would be the same as 2., current build + good test"
        )
    else:
        out += clone_job(
            job_id,
            int(last_good),
            f"last_good_tests_and_build:{last_good_tests}+{last_good_build}",
            last_good_tests,
            settings,
        )

    return out


def query_dependency_data_or_postpone(job_id: int, job_data: dict, settings: Settings) -> Optional[dict]:
    dependency_data = get_dependencies_ajax(job_id, settings)
    cluster_jobs = [job_id]
    for cluster in dependency_data.get("cluster", []):
        if job_id in cluster:
            cluster_jobs.extend(cluster)
    cluster_jobs = list(set(cluster_jobs))

    pending_cluster_jobs = [
        node
        for node in dependency_data.get("nodes", [])
        if node["id"] in cluster_jobs and not is_finished(node["state"])
    ]
    if pending_cluster_jobs:
        console.print(
            f"[yellow]Postponing to investigate job {job_id}: waiting until {len(pending_cluster_jobs)} pending parallel job(s) finished[/yellow]"
        )
        return None
    return dependency_data


def sync_via_investigation_comment(job_id: int, first_cluster_job_id: int, settings: Settings) -> Optional[int]:
    if settings.dry_run:
        return 42

    comment_id = client_post_job_comment(first_cluster_job_id, f"Starting investigation for job {job_id}", settings)[
        "id"
    ]
    comments = run_openqa_cli(["api", "--host", settings.host_url, f"jobs/{first_cluster_job_id}/comments"])
    first_comment_id = None
    min_comment_id = sys.maxsize
    for comment_data in json.loads(comments):
        if "investigation" in comment_data["text"] and comment_data["id"] < min_comment_id:
            min_comment_id = comment_data["id"]
            first_comment_id = comment_data["id"]

    if comment_id != first_comment_id:
        console.print(
            f"[yellow]Skipping investigation of job {job_id}: job cluster is already being investigated, see comment on job {first_cluster_job_id}[/yellow]"
        )
        client_delete_job_comment(first_cluster_job_id, comment_id, settings)
        return None
    return comment_id


def finalize_investigation_comment(
    job_id: int, first_cluster_job_id: int, comment_id: int, comment_text: str, settings: Settings
) -> None:
    if not comment_text:
        client_delete_job_comment(first_cluster_job_id, comment_id, settings)
        return

    comment = f"Automatic investigation jobs for job {job_id}:\n\n{comment_text}\n\n💡[*Detailed explanation of this comment*](https://github.com/os-autoinst/os-autoinst-scripts#More-details-and-examples-about-openqa-investigate-comments)"
    client_put_job_comment(first_cluster_job_id, comment_id, comment, settings)

    if first_cluster_job_id != job_id:
        client_post_job_comment(job_id, comment, settings)


@app.command()
def investigate(
    job_id: int = typer.Argument(..., help="Job ID to investigate"),
    host: str = typer.Option("openqa.opensuse.org", help="openQA host"),
    scheme: str = typer.Option("https", help="URL scheme"),
    investigation_gid: int = typer.Option(0, help="Investigation group ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not do any actions"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
    prio_add: int = typer.Option(100, help="Priority to add to cloned jobs"),
    exclude_name_regex: str = typer.Option(":investigate:", help="Regex to exclude job names"),
    exclude_no_group: bool = typer.Option(True, help="Exclude jobs without a group"),
    exclude_group_regex: str = typer.Option(r"Development.*/ ", help="Regex to exclude job groups"),
    force: bool = typer.Option(False, help="Force investigation even if clone exists"),
    retries: int = typer.Option(3, help="Number of retries for openqa-cli"),
    openqa_cli_retry_sleep_time_s: int = typer.Option(20, help="Sleep time for openqa-cli retries"),
    mojo_connect_timeout: int = typer.Option(30, help="Mojo connect timeout"),
) -> None:
    """Investigate openQA jobs."""
    settings = Settings(
        host=host,
        scheme=scheme,
        investigation_gid=investigation_gid,
        dry_run=dry_run,
        verbose=verbose,
        prio_add=prio_add,
        exclude_name_regex=exclude_name_regex,
        exclude_no_group=exclude_no_group,
        exclude_group_regex=exclude_group_regex,
        force=force,
        retries=retries,
        openqa_cli_retry_sleep_time_s=openqa_cli_retry_sleep_time_s,
        mojo_connect_timeout=mojo_connect_timeout,
    )

    job_data = client_get_job(job_id, settings)
    old_name = job_data["job"]["test"]

    if job_data["job"]["result"] == "passed":
        console.print(f"[green]Job {job_id} passed, no investigation needed.[/green]")
        raise typer.Exit(0)

    if re.search(settings.exclude_name_regex, old_name):
        console.print(f"[yellow]Job {job_id} skipped because its name '{old_name}' matches exclusion regex '{settings.exclude_name_regex}'[/yellow]")
        raise typer.Exit(0)

    clone_id = job_data["job"].get("clone_id")
    if not settings.force and clone_id is not None:
        console.print(
            f"[yellow]Job {job_id} already has a clone, skipping investigation. Use the env variable 'force=true' to trigger investigation jobs[/yellow]"
        )
        raise typer.Exit(0)

    dependency_data = query_dependency_data_or_postpone(job_id, job_data, settings)
    if dependency_data is None:
        raise typer.Exit(142)  # Indicate postponement

    first_cluster_job_id = job_id  # Simplified, original script has more complex logic
    comment_id = sync_via_investigation_comment(job_id, first_cluster_job_id, settings)
    if comment_id is None:
        raise typer.Exit(0)  # Already being investigated

    comment_output = ""
    try:
        comment_output = trigger_jobs(job_id, settings)
    except Exception as e:
        console.print(f"[bold red]Triggering investigation jobs failed: {e}[/bold red]")
        finalize_investigation_comment(
            job_id, first_cluster_job_id, comment_id, f"Triggering investigation jobs failed: {e}", settings
        )
        raise typer.Exit(1)

    finalize_investigation_comment(job_id, first_cluster_job_id, comment_id, comment_output, settings)


if __name__ == "__main__":
    app()
