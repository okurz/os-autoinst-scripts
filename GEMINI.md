# Project Overview

This project, `os-autoinst-scripts`, is a collection of automation scripts primarily designed to interact with openQA instances. Its main purpose is to streamline various tasks related to openQA job management, including automated review processes, investigation of failures, and custom hook executions. The project leverages a mix of Python and Perl scripting, along with Bash for shell-based operations.

**Main Technologies:**
*   **Python:** Used for various scripts, leveraging libraries like `requests` (for HTTP communication), `beautifulsoup4` (for HTML parsing), `typer` (for CLI applications), `httpx`, and `sh`.
*   **Perl:** Used for some core scripting functionalities, with dependencies managed via `cpanfile`.
*   **Bash:** For shell scripting and orchestration.

**Architecture:**
The project consists of individual scripts that can be called manually or automatically (e.g., in CI jobs). Key functionalities include:
*   **Auto-review:** Automatically labels openQA jobs with ticket references and can retrigger jobs based on regular expressions in progress.opensuse.org tickets.
*   **Investigation:** Triggers automated investigation jobs for unreviewed failures to determine the root cause (test regression, product regression, infrastructure issue, or sporadic issue).
*   **Hook Scripts:** Scripts designed to be called as custom job-done hooks within openQA.

# Building and Running

The project uses `uv` for Python dependency management and `make` for various build, test, and style-checking tasks.

## Dependencies

*   **Python Dependencies:** Listed in `pyproject.toml`.
*   **Perl Dependencies:** Listed in `dependencies.yaml`, which is used to generate `cpanfile`.
*   **System Dependencies:** System-level dependencies (e.g., `bash`, `coreutils`, `curl`, `jq`, `yq`, `sed`, `sudo`, `openQA-client`, `osc`, `openssh-clients`) are managed through the `os-autoinst-scripts-deps` package on openSUSE, which requires adding the openQA development repository.

To update Perl dependencies:
```bash
make update-deps
```

## Testing

### Unit Tests
```bash
make test-unit
# or more specifically for Python tests
PYTHONPATH=src:$(PYTHONPATH) uv run pytest
# or for Bash tests
make test-bash
```

### Style Checks
```bash
make checkstyle
# To automatically format shell files:
make shfmt
# To automatically format and fix Python files:
uv run ruff format
uv run ruff check --fix
```

### Functional Testing
Functional testing for some parts is done using the `test-tap-bash` library. Refer to the `Makefile` and `README.md` for specific examples, such as:
```bash
# Example for openqa-label-known-issues-multi dry run
cat tests/local_incompletes | env scheme=http host=localhost:9526 dry_run=1 sh -ex ./openqa-label-known-issues-multi
```

## Development Conventions

*   **Git Commit Messages:** Adhere to the conventions described in "How to Write a Git Commit Message".
*   **Python Linting & Formatting:** Enforced using `ruff` (configured in `pyproject.toml`).
*   **Shell Script Formatting:** Handled by `shfmt`.
*   **YAML Linting:** Handled by `yamllint`.
*   **Shell Script Linting:** Handled by `shellcheck`.
*   **Python Type Checking:** Performed using `pyright`.
*   **Docstrings:** Expected for modules, classes, and methods, though some specific docstring rules are currently ignored in `pyproject.toml`.

# Key Files and Directories

*   `README.md`: Project description and usage.
*   `Makefile`: Defines build, test, and style commands.
*   `pyproject.toml`: Python project configuration, dependencies, and linting rules.
*   `dependencies.yaml`: Lists Perl and system dependencies.
*   `openqa-powermanagement.py`: Python script for power management.
*   `racktables/`: Directory containing Python scripts for Racktables integration.
    *   `racktables/racktables.py`: Core library for Racktables API interaction.
    *   `racktables/get_unused_machines.py`: Script to retrieve unused machines from Racktables.
*   `tests/`: Directory containing unit and integration tests.
    *   `tests/test_openqa_bats_review.py`: Tests related to the openqa-bats-review functionality.
    *   `tests/test_chat_notify.py`: Tests for chat notification features.
    *   `tests/test_trigger_bisect_jobs.py`: Tests for triggering bisect jobs.
