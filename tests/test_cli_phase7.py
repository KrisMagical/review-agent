import json
import subprocess
import sys
from pathlib import Path

from app.report.cli_formatters import HtmlReportFormatter, JsonReportFormatter, MarkdownReportFormatter, TerminalReportFormatter, filter_issues


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", *args],
        input=input_text,
        capture_output=True,
        text=True,
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def sample_diff() -> str:
    return (
        "diff --git a/bad.py b/bad.py\n"
        "--- a/bad.py\n"
        "+++ b/bad.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+def run(cursor, user_id):\n"
        "+    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
        "+    return 42\n"
    )


def test_cli_help_commands() -> None:
    for args in [("--help",), ("file", "--help"), ("diff", "--help"), ("project", "--help")]:
        result = run_cli(*args)
        assert result.returncode == 0
        assert "usage:" in result.stdout


def test_file_command_formats_output_filtering_and_fail_on(tmp_path: Path) -> None:
    target = write(tmp_path / "bad.py", "def run(cursor, user_id):\n    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n")

    json_result = run_cli("file", str(target), "--format", "json")
    assert json_result.returncode == 0
    payload = json.loads(json_result.stdout)
    assert "issues" in payload
    assert "summary" in payload

    terminal_result = run_cli("file", str(target), "--format", "terminal")
    assert terminal_result.returncode == 0
    assert "MagicReview Report" in terminal_result.stdout

    markdown_result = run_cli("file", str(target), "--format", "markdown")
    assert markdown_result.returncode == 0
    assert "# MagicReview Report" in markdown_result.stdout

    html_result = run_cli("file", str(target), "--format", "html")
    assert html_result.returncode == 0
    assert "<!doctype html>" in html_result.stdout

    output_file = tmp_path / "report.md"
    output_result = run_cli("file", str(target), "--format", "markdown", "--output", str(output_file))
    assert output_result.returncode == 0
    assert output_result.stdout == ""
    assert "# MagicReview Report" in output_file.read_text(encoding="utf-8")

    filtered_result = run_cli("file", str(target), "--format", "json", "--severity", "high", "--max-issues", "1")
    filtered_payload = json.loads(filtered_result.stdout)
    assert filtered_payload["summary"]["total"] <= 1
    assert all(issue["severity"] in {"critical", "high"} for issue in filtered_payload["issues"])

    fail_result = run_cli("file", str(target), "--fail-on", "high")
    assert fail_result.returncode == 1


def test_diff_command_stdin_file_output_and_empty_diff(tmp_path: Path) -> None:
    stdin_result = run_cli("diff", "--format", "json", input_text=sample_diff())
    assert stdin_result.returncode == 0
    assert "issues" in json.loads(stdin_result.stdout)

    patch_file = write(tmp_path / "changes.patch", sample_diff())
    output_file = tmp_path / "diff-review.md"
    file_result = run_cli("diff", "--file", str(patch_file), "--format", "markdown", "--output", str(output_file))
    assert file_result.returncode == 0
    assert "MagicReview Report" in output_file.read_text(encoding="utf-8")

    empty_result = run_cli("diff", "--format", "json", input_text="")
    assert empty_result.returncode == 0
    assert json.loads(empty_result.stdout)["issues"] == []


def test_project_command_phase7_options(tmp_path: Path) -> None:
    write(tmp_path / "magicreview.yml", "rules:\n  max_parameters:\n    enabled: true\n    max_params: 1\n    severity: medium\n")
    write(tmp_path / "bad.py", "API_KEY = 'hardcoded'\ndef run(a, b):\n    return a + b\n")

    json_result = run_cli("project", str(tmp_path), "--format", "json")
    assert json_result.returncode == 0
    assert "issues" in json.loads(json_result.stdout)

    terminal_result = run_cli("project", str(tmp_path), "--format", "terminal")
    assert terminal_result.returncode == 0
    assert "Summary:" in terminal_result.stdout

    config_result = run_cli("project", str(tmp_path), "--config", str(tmp_path / "magicreview.yml"), "--format", "json")
    assert any(issue["type"] == "EnterpriseMaxParameters" for issue in json.loads(config_result.stdout)["issues"])

    no_enterprise_result = run_cli("project", str(tmp_path), "--no-enterprise", "--format", "json")
    assert all(issue["type"] != "EnterpriseMaxParameters" for issue in json.loads(no_enterprise_result.stdout)["issues"])

    llm_result = run_cli("project", str(tmp_path), "--llm", "--llm-provider", "mock", "--format", "json")
    assert llm_result.returncode == 0
    assert "issues" in json.loads(llm_result.stdout)

    agents_result = run_cli("project", str(tmp_path), "--agents", "--format", "json")
    assert agents_result.returncode == 0
    assert "issues" in json.loads(agents_result.stdout)

    subset_result = run_cli("project", str(tmp_path), "--agents", "quality,security", "--format", "json")
    subset_types = {issue["type"] for issue in json.loads(subset_result.stdout)["issues"]}
    assert "HardcodedSecretRisk" in subset_types


def test_report_formatters_and_html_escaping() -> None:
    result = {
        "issues": [
            {
                "severity": "high",
                "type": "XSS<Rule>",
                "file": "app/<bad>.py",
                "line": 3,
                "message": "<script>alert(1)</script>",
                "suggestion": "Use <safe> output.",
            }
        ]
    }

    assert "summary" in json.loads(JsonReportFormatter().format(result))
    assert "Summary:" in TerminalReportFormatter().format(result)
    assert "| Severity | Count |" in MarkdownReportFormatter().format(result)
    html = HtmlReportFormatter().format(result)
    assert "<!doctype html>" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_filter_issues_respects_severity_and_max() -> None:
    result = {
        "issues": [
            {"severity": "low", "type": "A", "file": "a.py", "line": 1, "message": "a", "suggestion": "a"},
            {"severity": "high", "type": "B", "file": "b.py", "line": 1, "message": "b", "suggestion": "b"},
            {"severity": "critical", "type": "C", "file": "c.py", "line": 1, "message": "c", "suggestion": "c"},
        ]
    }
    filtered = filter_issues(result, minimum_severity="high", max_issues=1)
    assert filtered["summary"]["total"] == 1
    assert filtered["issues"][0]["severity"] == "high"


def test_cli_argparse_error_returns_2() -> None:
    result = run_cli("project", ".", "--format", "xml")
    assert result.returncode == 2
