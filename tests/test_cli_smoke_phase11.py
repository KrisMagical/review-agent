import os
import subprocess
import sys


def _offline_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "REVIEWAGENT_LLM_PROVIDER": "none",
            "REVIEWAGENT_NETWORK_ENABLED": "false",
            "REVIEWAGENT_ALLOW_LLM": "false",
            "REVIEWAGENT_CODE_SHARING_MODE": "none",
        }
    )
    return env


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        env=_offline_env(),
        check=False,
    )


def test_review_console_help_and_version() -> None:
    help_result = _run(["review", "--help"])
    assert help_result.returncode == 0, help_result.stderr
    assert "ReviewAgent local CLI" in help_result.stdout

    version_result = _run(["review", "--version"])
    assert version_result.returncode == 0, version_result.stderr
    assert "ReviewAgent" in version_result.stdout


def test_python_module_cli_help() -> None:
    result = _run([sys.executable, "-m", "reviewagent.cli.main", "--help"])
    assert result.returncode == 0, result.stderr
    assert "ReviewAgent local CLI" in result.stdout
