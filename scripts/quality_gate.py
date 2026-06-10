"""Run ReviewAgent's local release quality gate.

The default gate avoids Docker so it works on lightweight Python environments.
Pass --docker to include Docker build and Compose validation.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ReviewAgent local quality gate.")
    parser.add_argument("--docker", action="store_true", help="Include Docker build/run and docker compose config.")
    args = parser.parse_args()

    commands = [
        [sys.executable, "-m", "pytest", "--basetemp=.pytest_tmp"],
        ["review", "--help"],
        ["review", "--version"],
        ["review", "file", "examples/bad_code.py", "--format", "json"],
        ["review", "project", "examples/multi_agent_project", "--agents", "--format", "json"],
        [sys.executable, "-m", "build", "--no-isolation"],
    ]
    if args.docker:
        commands.extend(
            [
                ["docker", "build", "-t", "reviewagent:test", "."],
                ["docker", "run", "--rm", "reviewagent:test", "review", "--help"],
                ["docker", "run", "--rm", "reviewagent:test", "review", "--version"],
                ["docker", "run", "--rm", "reviewagent:test", "python", "-m", "reviewagent.cli.main", "--help"],
                ["docker", "compose", "config"],
            ]
        )

    for command in commands:
        run(command)
    dist_files = sorted(str(path) for path in Path("dist").glob("*"))
    if not dist_files:
        raise RuntimeError("No distribution files found in dist/.")
    run(["twine", "check", *dist_files])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
