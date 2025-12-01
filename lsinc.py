#!/usr/bin/env python3
"""List incidents and associated packages of openQA jobs"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from itertools import chain, zip_longest
from urllib.parse import parse_qs, urlparse

import requests
from requests.exceptions import RequestException

BUGZILLA_TOKEN = os.getenv("BUGZILLA_TOKEN")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
OPENQA_HOST = os.environ.get("OPENQA_HOST", "openqa.suse.de")
TIMEOUT = 100
PACKAGE_WIDTH = 8
MAX_ISSUES = 200

BUGZILLA_ISSUES: list[dict] | None = []
JIRA_ISSUES: list[dict] | None = []

ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"

is_tty = sys.stdout.isatty()
session = requests.Session()


def get_bugzilla_issues(issues: list[str]) -> list[dict] | None:
    """Get Bugzilla issues"""
    if not BUGZILLA_TOKEN:
        return None

    issues = [i.split("=")[-1] for i in issues]
    url = "https://bugzilla.suse.com/rest/bug"
    bugs = []
    for i in range(0, len(issues), MAX_ISSUES):
        params = {
            "Bugzilla_api_key": BUGZILLA_TOKEN,
            "include_fields": "id,summary",
            "id": issues[i : i + MAX_ISSUES],
        }
        try:
            got = session.get(url, params=params, timeout=TIMEOUT)
            got.raise_for_status()
        except RequestException as error:
            print(f"ERROR: {url}: {error}", file=sys.stderr)
            return None
        bugs.extend(got.json()["bugs"])
    return bugs


def get_jira_issues(issues: list[str]) -> list[dict] | None:
    """Get Jira issues"""
    if not JIRA_TOKEN:
        return None
    issues = [os.path.basename(i) for i in issues]
    url = "https://jira.suse.com/rest/api/2/search"
    headers = {"Authorization": f"Bearer {JIRA_TOKEN}"}
    bugs = []
    for i in range(0, len(issues), MAX_ISSUES):
        params = {
            "fields": "summary",
            "jql": f"key in ({','.join(issues[i : i + MAX_ISSUES])})",
        }
        try:
            got = session.get(url, headers=headers, params=params, timeout=TIMEOUT)
            got.raise_for_status()
        except RequestException as exc:
            print(f"ERROR: {url}: {exc}", file=sys.stderr)
            return None
        bugs.extend([{"id": issue["key"], "summary": issue["fields"]["summary"]} for issue in got.json()["issues"]])
    return bugs


def get_title(url: str) -> str:
    """Get title for Bugzilla or Jira issue"""
    if not url:
        return ""
    issue_id: int | str | None = None
    issues: list[dict] | None = None
    if "bugzilla.suse.com" in url:
        issue_id = int(url.rsplit("=", maxsplit=1)[-1])
        issues = BUGZILLA_ISSUES
    elif "jira.suse.com" in url:
        issue_id = os.path.basename(url)
        issues = JIRA_ISSUES
    if issues:
        for issue in issues:
            if issue["id"] == issue_id:
                return issue["summary"]
    return ""


def get_incidents(route: str) -> list[dict]:
    """Fetch data from SMELT"""
    url = f"https://smelt.suse.de/api/v1/overview/{route}/"
    got = session.get(url)
    got.raise_for_status()
    data = got.json()
    results = data["results"]
    while data["next"]:
        got = session.get(data["next"])
        got.raise_for_status()
        data = got.json()
        results += data["results"]
    return results


@cache
def get_all_incidents() -> list[dict]:
    """Get all incidents"""
    routes = ["tested_declined", "tested_ready", "testing"]
    with ThreadPoolExecutor(max_workers=len(routes)) as executor:
        results = executor.map(get_incidents, routes)
    incidents = list(chain.from_iterable(results))
    return incidents


def get_api_url(job: str) -> str:
    """Get API URL from job string which may be job ID or URL"""
    if job.isdigit():
        return f"https://{OPENQA_HOST}/api/v1/jobs/{job}"

    # Add scheme if missing so we can use urlparse()
    if job.startswith("http://"):
        job = job.removeprefix("http://")
    if not job.startswith("https://"):
        job = f"https://{job}"

    url = urlparse(job)
    if url.query:
        base_url = f"{url.scheme}://{url.netloc}/api/v1/jobs/overview"
        params: dict[str, list[str]] = parse_qs(url.query)
        try:
            got = session.get(base_url, params=params, timeout=TIMEOUT)
            got.raise_for_status()
            data = got.json()
        except RequestException as error:
            sys.exit(f"ERROR: {job}: {error}")
        assert len(data) == 1
        job = str(data[0]["id"])
    else:
        # Support both "$OPENQA_HOST/t1234" & "$OPENQA_HOST/tests/1234"
        job = os.path.basename(url.path).removeprefix("t")

    assert job.isdigit()
    return f"https://{url.netloc}/api/v1/jobs/{job}"


def fetch_job(job: str) -> dict:
    """Return job information from openQA"""
    url = get_api_url(job)
    req = session.get(url)
    req.raise_for_status()
    return req.json()["job"]


def fetch_incident(incident_id: int) -> dict | None:
    """Return incident information"""
    for incident in get_all_incidents():
        if incident["incident"]["incident_id"] == incident_id:
            return incident
    return None


def print_incident(incident_id: int | dict, verbose: bool = False) -> None:
    """Print information for incident"""
    if isinstance(incident_id, int):
        incident = fetch_incident(incident_id)
        if incident is None:
            print(f"ERROR: {incident_id}: NOT FOUND", file=sys.stderr)
            return
    else:
        incident = incident_id
    packages = sorted(incident["packages"])
    if verbose:
        refs = [_["url"] for _ in incident["incident"]["references"] if not _["name"].startswith("CVE-")]
    else:
        refs = [_["name"] for _ in incident["incident"]["references"] if not _["name"].startswith("CVE-")]
    refs = sorted(refs) or [""]
    fmt = f"{{:<16}}  {{:{PACKAGE_WIDTH}}}  {{:50}}"
    sm_id = incident["incident"]["project"].replace("SUSE:Maintenance", "S:M")
    sm_id += f":{incident['request_id']}"
    status = incident["status"]["name"]
    if is_tty:
        if status == "ready":
            sm_id = f"{ANSI_GREEN}{sm_id}{ANSI_RESET}"
        elif status == "declined":
            sm_id = f"{ANSI_RED}{sm_id}{ANSI_RESET}"
    if verbose:
        fmt += "  {}"
        print(fmt.format(sm_id, packages[0], refs[0], get_title(refs[0])))
        for package, url in zip_longest(packages[1:], refs[1:], fillvalue=""):
            print(fmt.format("", package, url, get_title(url)))
    else:
        print(fmt.format(sm_id, ",".join(packages), ",".join(refs)))


def run_diff(job1: str, job2: str) -> None:
    """Show differences between 2 jobs"""

    def get_issues(job: dict) -> set[int]:
        settings = job["settings"]
        incidents = []
        for issue in [x for x in settings if "_TEST_ISSUES" in x]:
            incidents += [int(x.strip()) for x in settings[issue].split(",")]
        return set(incidents)  # remove duplicates

    print(f"Diff between {get_api_url(job1)} and {get_api_url(job2)}")

    inc1 = get_issues(fetch_job(job1))
    inc2 = get_issues(fetch_job(job2))

    # List diff plus
    plus = [x for x in inc2 if x not in inc1]
    for p in plus:
        sys.stdout.write("+")
        print_incident(p)
    # List diff minus
    minus = [x for x in inc1 if x not in inc2]
    for m in minus:
        sys.stdout.write("-")
        print_incident(m)

    if len(plus) == 0 and len(minus) == 0:
        print("diff _TEST_ISSUES is empty", file=sys.stderr)


def main() -> None:
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("jobs", help="openQA jobs go here", nargs="+")
    parser.add_argument("-d", "--diff", help="List only the diff between two jobs", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Calculate maximum package string length
    global PACKAGE_WIDTH  # pylint: disable=global-statement
    PACKAGE_WIDTH = max(len(package) for inc in get_all_incidents() for package in inc["packages"])

    jobs = args.jobs
    if args.diff:
        if len(jobs) != 2:
            sys.exit("ERROR: job diff requires exactly two jobs")
        run_diff(jobs[0], jobs[1])
    else:
        if args.verbose:
            global BUGZILLA_ISSUES
            BUGZILLA_ISSUES = get_bugzilla_issues([
                u["url"]
                for i in get_all_incidents()
                for u in i["incident"]["references"]
                if "bugzilla.suse.com" in u["url"]
            ])
            global JIRA_ISSUES
            JIRA_ISSUES = get_jira_issues([
                u["url"]
                for i in get_all_incidents()
                for u in i["incident"]["references"]
                if "jira.suse.com" in u["url"]
            ])
        for job in jobs:
            job = fetch_job(job)
            settings = job["settings"]
            ids = set()
            for issue in [x for x in settings if "_TEST_ISSUES" in x]:
                ids |= set(int(x.strip()) for x in settings[issue].split(","))
            incidents = [i for i in get_all_incidents() if i["incident"]["incident_id"] in ids]
            incidents.sort(key=lambda i: str.casefold(i["packages"][0]))
            for incident in incidents:
                print_incident(incident, args.verbose)
            not_found = ids - {i["incident"]["incident_id"] for i in incidents}
            for id_ in sorted(not_found):
                print(f"NOT FOUND: {id_}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Cancelled")
    finally:
        session.close()
