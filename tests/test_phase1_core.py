import json
import subprocess
import sys
from pathlib import Path

from app.analyzers.ast_analyzer import ASTAnalyzer
from app.models.issue import Issue
from app.rules.engine import RuleEngine


def issue_types(source: str) -> set[str]:
    return {issue.type for issue in ASTAnalyzer().analyze_file("sample.py", source)}


def test_issue_model_json_serialization() -> None:
    issue = Issue(
        severity="medium",
        type="FunctionTooLongRule",
        file="sample.py",
        line=10,
        message="Function is too long.",
        suggestion="Split it.",
    )

    assert json.loads(issue.model_dump_json()) == {
        "severity": "medium",
        "type": "FunctionTooLongRule",
        "file": "sample.py",
        "line": 10,
        "message": "Function is too long.",
        "suggestion": "Split it.",
    }


def test_rule_engine_registers_and_runs_rules() -> None:
    issues = RuleEngine().review_source(file_path="sample.py", source_code="def run(a):\n    return a + 3\n")

    assert {issue.type for issue in issues} >= {"TypeHintRule", "MagicNumberRule"}


def test_function_too_long_hit_and_no_false_positive() -> None:
    long_body = "\n".join("    pass" for _ in range(81))
    assert "FunctionTooLongRule" in issue_types(f"def long_function() -> None:\n{long_body}\n")
    assert "FunctionTooLongRule" not in issue_types("def short() -> None:\n    pass\n")


def test_too_many_parameters_hit_and_no_false_positive() -> None:
    assert "TooManyParametersRule" in issue_types("def run(a, b, c, d, e, f) -> None:\n    pass\n")
    assert "TooManyParametersRule" not in issue_types("def run(a, b, c) -> None:\n    pass\n")


def test_type_hint_hit_and_no_false_positive() -> None:
    assert "TypeHintRule" in issue_types("def run(a):\n    return a\n")
    assert "TypeHintRule" not in issue_types("def run(a: int) -> int:\n    return a\n")


def test_magic_number_hit_and_no_false_positive() -> None:
    assert "MagicNumberRule" in issue_types("def run(a: int) -> int:\n    return a + 42\n")
    assert "MagicNumberRule" not in issue_types("MAX_RETRY = 3\ndef run(a: int) -> int:\n    return a + 2\n")


def test_none_risk_hit_and_no_false_positive() -> None:
    assert "NoneRiskRule" in issue_types("def run(data: dict) -> str:\n    user = data.get('user')\n    return user.name\n")
    assert "NoneRiskRule" not in issue_types(
        "def run(data: dict) -> str:\n    user = data.get('user')\n    if user is not None:\n        return user.name\n    return ''\n"
    )


def test_index_risk_hit_and_no_false_positive() -> None:
    assert "IndexRiskRule" in issue_types("def run(items: list[int]) -> int:\n    return items[0]\n")
    assert "IndexRiskRule" not in issue_types(
        "def run(items: list[int]) -> int | None:\n    if items:\n        return items[0]\n    return None\n"
    )


def test_key_error_hit_and_no_false_positive() -> None:
    assert "KeyErrorRule" in issue_types("def run(data: dict) -> str:\n    return data['name']\n")
    assert "KeyErrorRule" not in issue_types(
        "def run(data: dict) -> str | None:\n    if 'name' in data:\n        return data['name']\n    return None\n"
    )


def test_zero_division_hit_and_no_false_positive() -> None:
    assert "ZeroDivisionRule" in issue_types("def run(total: int, count: int) -> float:\n    return total / count\n")
    assert "ZeroDivisionRule" not in issue_types(
        "def run(total: int, count: int) -> float | None:\n    if count != 0:\n        return total / count\n    return None\n"
    )


def test_file_leak_hit_and_no_false_positive() -> None:
    assert "FileLeakRule" in issue_types("def run(path: str) -> str:\n    f = open(path)\n    return f.read()\n")
    assert "FileLeakRule" not in issue_types("def run(path: str) -> str:\n    with open(path) as f:\n        return f.read()\n")


def test_sql_injection_hit_and_no_false_positive() -> None:
    assert "SQLInjectionRule" in issue_types(
        "def run(cursor, user_id: str) -> None:\n    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
    )
    assert "SQLInjectionRule" not in issue_types(
        "def run(cursor, user_id: str) -> None:\n    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))\n"
    )


def test_path_traversal_hit_and_no_false_positive() -> None:
    assert "PathTraversalRule" in issue_types("def run(user_path: str) -> str:\n    return open(user_path).read()\n")
    assert "PathTraversalRule" not in issue_types(
        "def run(user_path: str) -> str:\n    safe_path = safe_join('/tmp', user_path)\n    return open(safe_path).read()\n"
    )


def test_review_file_cli_outputs_json(tmp_path: Path) -> None:
    target = tmp_path / "bad.py"
    target.write_text("def run(a):\n    return a + 42\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "file", str(target)],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert "issues" in payload
    assert {issue["type"] for issue in payload["issues"]} >= {"TypeHintRule", "MagicNumberRule"}


def test_review_diff_cli_outputs_json() -> None:
    diff_text = """diff --git a/app/bad.py b/app/bad.py
index 1111111..2222222 100644
--- a/app/bad.py
+++ b/app/bad.py
@@ -0,0 +1,2 @@
+def run(a):
+    return a + 42
"""

    result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "diff"],
        input=diff_text,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert "issues" in payload
    assert {issue["type"] for issue in payload["issues"]} >= {"TypeHintRule", "MagicNumberRule"}
