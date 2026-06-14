import os
import subprocess
import sys


def _offline_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "MGREVIEW_LLM_PROVIDER": "none",
            "MGREVIEW_NETWORK_ENABLED": "false",
            "MGREVIEW_ALLOW_LLM": "false",
            "MGREVIEW_CODE_SHARING_MODE": "none",
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
    help_result = _run([sys.executable, "-m", "magicreview.cli.main", "--help"])
    assert help_result.returncode == 0, help_result.stderr
    assert "MagicReview" in help_result.stdout
    assert "local-first, self-hostable AI code review platform" in help_result.stdout

    version_result = _run([sys.executable, "-m", "magicreview.cli.main", "--version"])
    assert version_result.returncode == 0, version_result.stderr
    assert version_result.stdout.strip() == "MagicReview 0.1.2"


def test_python_module_cli_help() -> None:
    result = _run([sys.executable, "-m", "magicreview.cli.main", "--help"])
    assert result.returncode == 0, result.stderr
    assert "MagicReview" in result.stdout
