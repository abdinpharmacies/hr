#!/usr/bin/env python3
"""Report recent commits that have not been cherry-picked to another branch."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "commit_cherry_pick_report.toml"
DEFAULT_OUTPUT = SCRIPT_DIR / "commit_cherry_pick_report.txt"
FIELD_SEPARATOR = "\x1f"
RECORD_SEPARATOR = "\x1e"
CHERRY_PICK_TRAILER = re.compile(
    r"^\s*\(cherry picked from commit ([0-9a-f]{40,64})\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class ReportError(Exception):
    """Raised for configuration and Git command errors."""


@dataclass(frozen=True)
class Config:
    working_branch: str
    picker_branch: str
    last_x_days: int


@dataclass(frozen=True)
class Commit:
    sha: str
    author: str
    authored_at: str
    subject: str
    parents: tuple[str, ...]

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List recent commits on two branches and show working-branch "
            "commits not cherry-picked to the picker branch."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"TOML configuration file (default: {DEFAULT_CONFIG.name})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Report output file (default: {DEFAULT_OUTPUT.name})",
    )
    return parser.parse_args()


def fail(message: str) -> NoReturn:
    raise ReportError(message)


def load_config(path: Path) -> Config:
    try:
        with path.expanduser().open("rb") as config_file:
            values = tomllib.load(config_file)
    except FileNotFoundError:
        fail(f"Configuration file not found: {path}")
    except tomllib.TOMLDecodeError as error:
        fail(f"Invalid TOML in {path}: {error}")
    except OSError as error:
        fail(f"Cannot read configuration file {path}: {error}")

    required = {"working_branch", "picker_branch", "last_x_days"}
    missing = sorted(required - values.keys())
    if missing:
        fail(f"Missing configuration value(s): {', '.join(missing)}")

    unexpected = sorted(values.keys() - required)
    if unexpected:
        fail(f"Unknown configuration value(s): {', '.join(unexpected)}")

    working_branch = values["working_branch"]
    picker_branch = values["picker_branch"]
    last_x_days = values["last_x_days"]

    if not isinstance(working_branch, str) or not working_branch.strip():
        fail("working_branch must be a non-empty string")
    if not isinstance(picker_branch, str) or not picker_branch.strip():
        fail("picker_branch must be a non-empty string")
    if working_branch == picker_branch:
        fail("working_branch and picker_branch must be different")
    if isinstance(last_x_days, bool) or not isinstance(last_x_days, int):
        fail("last_x_days must be an integer")
    if last_x_days < 1:
        fail("last_x_days must be at least 1")

    return Config(
        working_branch=working_branch,
        picker_branch=picker_branch,
        last_x_days=last_x_days,
    )


def run_git(
    repository: Path,
    arguments: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "--no-pager", *arguments],
            cwd=repository,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        fail("Git is not installed or is not available on PATH")
    except OSError as error:
        fail(f"Unable to run Git: {error}")

    if check and result.returncode != 0:
        command = "git " + " ".join(arguments)
        detail = result.stderr.strip() or "unknown Git error"
        fail(f"Command failed ({command}): {detail}")
    return result


def find_repository() -> Path:
    result = run_git(
        SCRIPT_DIR,
        ["rev-parse", "--show-toplevel"],
        check=False,
    )
    if result.returncode != 0:
        fail(f"Script directory is not inside a Git repository: {SCRIPT_DIR}")
    return Path(result.stdout.strip())


def resolve_ref(repository: Path, ref: str, setting_name: str) -> str:
    result = run_git(
        repository,
        ["rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}"],
        check=False,
    )
    if result.returncode != 0:
        fail(f"{setting_name} does not resolve to a commit: {ref}")
    return result.stdout.strip()


def recent_commits(repository: Path, ref: str, days: int) -> list[Commit]:
    log_format = FIELD_SEPARATOR.join(["%H", "%an", "%aI", "%s", "%P"])
    result = run_git(
        repository,
        [
            "log",
            f"--since={days} days ago",
            "--date-order",
            f"--format={log_format}{RECORD_SEPARATOR}",
            ref,
            "--",
        ],
    )

    commits: list[Commit] = []
    for raw_record in result.stdout.split(RECORD_SEPARATOR):
        record = raw_record.strip("\n")
        if not record:
            continue
        fields = record.split(FIELD_SEPARATOR)
        if len(fields) != 5:
            fail(f"Unexpected Git log output while reading {ref}")
        sha, author, authored_at, subject, raw_parents = fields
        commits.append(
            Commit(
                sha=sha,
                author=author,
                authored_at=authored_at,
                subject=subject,
                parents=tuple(raw_parents.split()),
            )
        )
    return commits


def picker_coverage(repository: Path, picker_branch: str) -> set[str]:
    result = run_git(
        repository,
        ["log", "--format=%H%x1f%B%x1e", picker_branch, "--"],
    )

    covered: set[str] = set()
    for raw_record in result.stdout.split(RECORD_SEPARATOR):
        record = raw_record.strip("\n")
        if not record:
            continue
        try:
            sha, message = record.split(FIELD_SEPARATOR, 1)
        except ValueError:
            fail(f"Unexpected Git log output while reading {picker_branch}")
        covered.add(sha.lower())
        covered.update(match.lower() for match in CHERRY_PICK_TRAILER.findall(message))
    return covered


def print_history(title: str, commits: Sequence[Commit]) -> None:
    print(f"\n=== {title} ({len(commits)}) ===")
    if not commits:
        print("No commits found in the configured date range.")
        return

    for commit in commits:
        marker = " [merge]" if commit.is_merge else ""
        print(
            f"{commit.sha}  {commit.authored_at}  "
            f"{commit.author}  {commit.subject}{marker}"
        )


def show_missing_commits(repository: Path, commits: Sequence[Commit]) -> None:
    print(f"\n=== Missing cherry-picks ({len(commits)}) ===")
    if not commits:
        print("All recent non-merge working-branch commits are covered.")
        return

    for index, commit in enumerate(commits):
        if index:
            print("\n" + "=" * 80 + "\n")
        result = run_git(
            repository,
            [
                "show",
                "--no-color",
                "--no-ext-diff",
                "--format=fuller",
                "--stat",
                "--patch",
                commit.sha,
                "--",
            ],
        )
        print(result.stdout.rstrip())


def addon_module_names(repository: Path) -> set[str]:
    return {
        path.parent.name
        for path in repository.glob("*/__manifest__.py")
        if path.is_file()
    }


def changed_modules(
    repository: Path,
    commit_sha: str,
    available_modules: set[str],
) -> tuple[str, ...]:
    result = run_git(
        repository,
        [
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "--no-renames",
            "-r",
            commit_sha,
            "--",
        ],
    )
    touched_modules = {
        path.split("/", 1)[0]
        for path in result.stdout.splitlines()
        if "/" in path and path.split("/", 1)[0] in available_modules
    }
    return tuple(sorted(touched_modules))


def print_missing_summary(repository: Path, commits: Sequence[Commit]) -> None:
    print("\n=== Missing cherry-pick summary ===")
    if not commits:
        print("No missing commits.")
        return

    available_modules = addon_module_names(repository)
    for commit in commits:
        modules = changed_modules(repository, commit.sha, available_modules)
        module_list = ", ".join(modules) if modules else "(no addon module)"
        print(
            f"{commit.sha} - {module_list} - "
            f"{commit.author} - {commit.authored_at}"
        )


def write_report(arguments: argparse.Namespace) -> None:
    config = load_config(arguments.config)
    repository = find_repository()

    working_tip = resolve_ref(repository, config.working_branch, "working_branch")
    picker_tip = resolve_ref(repository, config.picker_branch, "picker_branch")

    working_commits = recent_commits(
        repository,
        working_tip,
        config.last_x_days,
    )
    picker_commits = recent_commits(
        repository,
        picker_tip,
        config.last_x_days,
    )
    covered_shas = picker_coverage(repository, picker_tip)
    missing_commits = [
        commit
        for commit in working_commits
        if not commit.is_merge and commit.sha.lower() not in covered_shas
    ]

    print(
        f"Commit report: last {config.last_x_days} day(s) | "
        f"working={config.working_branch} | picker={config.picker_branch}"
    )
    print_history(f"Recent commits on {config.working_branch}", working_commits)
    print_history(f"Recent commits on {config.picker_branch}", picker_commits)
    show_missing_commits(repository, missing_commits)
    print(f"\nMissing cherry-pick count: {len(missing_commits)}")
    print_missing_summary(repository, missing_commits)


def main() -> int:
    arguments = parse_arguments()
    output_path = arguments.output.expanduser()
    try:
        with output_path.open("w", encoding="utf-8") as output_file:
            with redirect_stdout(output_file):
                write_report(arguments)
    except OSError as error:
        fail(f"Cannot write report file {output_path}: {error}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ReportError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)
