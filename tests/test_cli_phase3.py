import json
import subprocess
import sys
from pathlib import Path


def test_cli_file_diff_project_still_return_json(tmp_path: Path) -> None:
    target = tmp_path / "bad.py"
    target.write_text("def run(a):\n    return a + 42\n", encoding="utf-8")

    file_result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "file", str(target)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "issues" in json.loads(file_result.stdout)

    diff_text = (
        "diff --git a/bad.py b/bad.py\n"
        "--- a/bad.py\n"
        "+++ b/bad.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def run(a):\n"
        "+    return a + 42\n"
    )
    diff_result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "diff"],
        input=diff_text,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "issues" in json.loads(diff_result.stdout)

    project_result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "project", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "issues" in json.loads(project_result.stdout)
