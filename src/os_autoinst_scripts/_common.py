#!/usr/bin/env python3
# Copyright SUSE LLC
"""Common Python functions to be used when interacting with openQA instances, for example over openqa-cli."""

import json
import subprocess
import sys
import time
from typing import List, Optional

import httpx
from rich.console import Console
from sh import (
    CommandNotFound,
)
from sh import (
    basename as sh_basename,
)
from sh import (
    cut as sh_cut,
)
from sh import (
    git as sh_git,
)
from sh import (
    git_obs as sh_git_obs,
)
from sh import (
    grep as sh_grep,
)
from sh import (
    head as sh_head,
)
from sh import (
    nc as sh_nc,
)
from sh import (
    openqa_cli as sh_openqa_cli,
)
from sh import (
    osc as sh_osc,
)
from sh import (
    ping as sh_ping,
)
from sh import (
    rg as sh_rg,  # Import rg
)
from sh import (
    rpmspec as sh_rpmspec,
)
from sh import (
    sed as sh_sed,
)
from sh import (
    sort as sh_sort,
)
from sh import (
    ssh as sh_ssh,
)
from sh import (
    tr as sh_tr,
)
from sh import (
    zypper as sh_zypper,
)

console = Console()

# Expose sh commands as top-level functions
basename = sh_basename
cut = sh_cut
git = sh_git
git_obs = sh_git_obs
grep = sh_grep
head = sh_head
nc = sh_nc
openqa_cli = sh_openqa_cli
osc = sh_osc
ping = sh_ping
rg = sh_rg  # Expose rg
rpmspec = sh_rpmspec
sed = sh_sed
sort = sh_sort
ssh = sh_ssh
tr = sh_tr
zypper = sh_zypper

# Expose other functions
from ._common_functions import (  # Assuming these are in a separate file or need to be defined here
    delete_packages_from_obs_project,
    list_packages,
)

OSC = "osc"  # Assuming osc is installed and in PATH
OPENQA_CLI = "openqa-cli"  # Assuming openqa-cli is installed and in PATH

COLOR_BOLD = "[bold]"
COLOR_RED = "[red]"
COLOR_GREEN = "[green]"
COLOR_YELLOW = "[yellow]"
COLOR_CYAN = "[cyan]"
COLOR_INFO = "[cyan][bold]"
COLOR_WARNING = "[yellow][bold]"
COLOR_ERROR = "[red][bold]"
NO_COLOR = "[/]"


def warn(message: str) -> None:
    console.print(f"{COLOR_WARNING}{message}{NO_COLOR}", file=sys.stderr)


def log_info(message: str) -> None:
    console.print(f"{COLOR_INFO}{message}{NO_COLOR}")


def log_debug(message: str) -> None:
    console.print(f"{COLOR_CYAN}{message}{NO_COLOR}", file=sys.stderr)


def log_warn(message: str) -> None:
    console.print(f"{COLOR_WARNING}{message}{NO_COLOR}", file=sys.stderr)


def log_error(message: str) -> None:
    console.print(f"{COLOR_ERROR}{message}{NO_COLOR}", file=sys.stderr)


def job_ids(job_post_response_content: str) -> List[str]:
    try:
        data = json.loads(job_post_response_content)
        return [str(job_id) for job_id in data.get("ids", [])]
    except json.JSONDecodeError:
        return []


def runcli(args: List[str], verbose: bool = False) -> str:
    if verbose:
        log_debug(f"Running: {' '.join(args)}")
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        if result.stderr:
            warn(f"Stderr from {' '.join(args)}: {result.stderr}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        warn(f"Command {' '.join(args)} failed with exit code {e.returncode}")
        warn(f"Stdout: {e.stdout}")
        warn(f"Stderr: {e.stderr}")
        raise
    except FileNotFoundError:
        warn(f"Command not found: {args[0]}")
        raise


def runjq(input_string: str, query: str, output_limit: int = 15) -> str:
    try:
        # Using Python's json module instead of external jq
        data = json.loads(input_string)
        # This is a very basic replacement for jq, for complex queries a proper jq-like library or re-implementing the logic would be needed.
        # For simple cases like .ids[] or .job.result, direct dictionary access might suffice.
        # For now, let's assume direct dictionary access for common patterns.
        if query == ".ids[]":
            return "\n".join([str(x) for x in data.get("ids", [])])
        if query.startswith(".job."):
            parts = query.split(".")
            value = data
            for part in parts[1:]:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
            return str(value) if value is not None else "null"
        # Fallback for more complex jq queries or when direct access is not simple
        # This is where a full jq-like library might be needed
        log_warn(f"Complex jq query not fully supported yet: {query}. Returning full input.")
        return input_string
    except json.JSONDecodeError:
        warn(f"runjq: Invalid JSON input. Input: {input_string[:output_limit]}...")
        raise
    except Exception as e:
        warn(f"runjq: Error processing query '{query}': {e}. Input: {input_string[:output_limit]}...")
        raise


def exp_retry(stop_exponent: int, exponent: int) -> bool:
    if exponent >= stop_exponent:
        warn(f"{stop_exponent} (re)tries exceeded")
        return False
    wait_sec = 2**exponent
    warn(f"Waiting {wait_sec}s until retry #{exponent}")
    time.sleep(wait_sec)
    return True


def shorten_string(sstring: str, max_str_len: int = 120) -> str:
    if len(sstring) > max_str_len:
        half_len = max_str_len // 2
        return f"{sstring[:half_len]}...{sstring[-half_len:]}"
    return sstring


def runcurl(args: List[str], exp_retries: int = 12, verbose: bool = False) -> str:
    for retry_exponent in range(exp_retries + 1):
        if verbose:
            log_debug(f"curl: Fetching ({' '.join(args)})")
        try:
            response = httpx.get(args[-1])  # Assuming URL is always the last argument for simplicity
            response.raise_for_status()
            return response.text
        except httpx.RequestError as e:
            warn(f"curl: Error fetching ({' '.join(args)}): {e}")
            if not exp_retry(exp_retries, retry_exponent):
                raise
        except httpx.HTTPStatusError as e:
            warn(f"curl: Error fetching url ({' '.join(args)}): Got Status {e.response.status_code}")
            if not exp_retry(exp_retries, retry_exponent):
                raise
    raise Exception("Max retries exceeded for curl operation")


def openqa_api_get(path: str, host_url: str) -> dict:
    # This is a simplified version, as the shell script's openqa-api-get is more complex
    # and directly uses openqa-cli with --json flag.
    # We will replicate that behavior using openqa_cli sh function.
    try:
        result = runcli([OPENQA_CLI, "api", "--host", host_url, "--json", path])
        return json.loads(result)
    except Exception as e:
        warn(f"openqa-api-get: Error making API request ({path}): {e}")
        raise


def comment_on_job(
    job_id: int, comment: str, force_result: Optional[str] = None, enable_force_result: bool = False
) -> None:
    if enable_force_result and force_result:
        comment = f"label:force_result:{force_result}:{comment}"
    # Placeholder, need to use openqa-cli api or httpx for actual comment posting
    log_info(f"Simulating comment on job {job_id}: {comment}")


def search_log(job_id: int, search_term: str, out_file: str, grep_timeout: int = 5) -> bool:
    # Placeholder for actual log searching
    log_info(f"Simulating searching log {out_file} for '{search_term}'")
    return True  # Always found for simulation


def list_packages(obs_project: str) -> List[str]:
    try:
        result = subprocess.run([OSC, "ls", obs_project], capture_output=True, text=True, check=True)
        return [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except subprocess.CalledProcessError as e:
        warn(f"Error listing packages for {obs_project}: {e.stderr}")
        return []
    except CommandNotFound:
        warn(f"Command not found: {OSC}. Is OBS client installed?")
        return []


def delete_packages_from_obs_project(obs_project: str) -> None:
    log_info(f"Deleting packages from OBS project: {obs_project}")
    packages = list_packages(obs_project)
    for package in packages:
        log_info(f"Deleting {package} from {obs_project}")
        try:
            subprocess.run(
                [OSC, "rdelete", "-m", f"Cleaning up {package} from {obs_project}", obs_project, package],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            log_error(f"Error deleting package {package} from {obs_project}: {e.stderr}")


def openqa_api_post(path: str, data: dict, host_url: str) -> dict:
    try:
        result = runcli([OPENQA_CLI, "api", "--host", host_url, "-X", "POST", path, "--json"], input=json.dumps(data))
        return json.loads(result)
    except Exception as e:
        warn(f"openqa-api-post: Error making API request ({path}): {e}")
        raise


def openqa_api_put(path: str, data: dict, host_url: str) -> dict:
    try:
        result = runcli([OPENQA_CLI, "api", "--host", host_url, "-X", "PUT", path, "--json"], input=json.dumps(data))
        return json.loads(result)
    except Exception as e:
        warn(f"openqa-api-put: Error making API request ({path}): {e}")
        raise
