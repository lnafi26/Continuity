#!/usr/bin/env python3
"""Read-only migration gate for Continuity's GitHub integration."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

APPROVED = (
    "20261016000000_initial_schema.sql",
    "20261030212002_continuity_b1_privilege_hardening.sql",
)

DEFERRED = "20261017000000_processing_jobs.sql"


def migration_files(ref):
    output = subprocess.check_output(
        [
            "git", "ls-tree", "-r", "--name-only",
            ref, "--", "supabase/migrations",
        ],
        cwd=ROOT,
        text=True,
    )

    return tuple(sorted(
        Path(name).name
        for name in output.splitlines()
        if name.endswith(".sql")
    ))


def assess(main_files, staging_files):
    problems = []

    if tuple(main_files) != APPROVED:
        problems.append(
            "main does not contain exactly the approved migrations"
        )

    if tuple(staging_files) != APPROVED:
        problems.append(
            "staging does not contain exactly the approved migrations"
        )

    if DEFERRED in main_files or DEFERRED in staging_files:
        problems.append(
            "deferred processing_jobs migration is discoverable"
        )

    return problems


def main():
    try:
        main_files = migration_files("origin/main")
        staging_files = migration_files("origin/staging")
    except subprocess.CalledProcessError:
        print("STOP: Fetch origin/main and origin/staging first.")
        return 2

    print("Continuity Supabase integration preflight")
    print()
    print("main migrations:", list(main_files))
    print("staging migrations:", list(staging_files))
    print()

    problems = assess(main_files, staging_files)

    if problems:
        print("BLOCKED: Migration branches are not aligned.")
        for problem in problems:
            print(" -", problem)

        print()
        print("Do not enable automatic Supabase deployment.")
        return 2

    print("Migration manifests aligned.")
    print("This does NOT authorize automatic deployment.")
    print("Separate integration approval is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
