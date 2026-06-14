"""Map magicreview issues to GitHub pull request diff lines."""

from __future__ import annotations

from app.parser.diff_parser import DiffParser


class DiffLineMapper:
    """Track PR diff added lines that GitHub can receive RIGHT-side comments for."""

    def __init__(self, diff_text: str) -> None:
        self.changed_lines = {
            file_path: set(file_diff.all_changed_lines)
            for file_path, file_diff in DiffParser.parse(diff_text).items()
        }

    def can_comment(self, file_path: str, line: int) -> bool:
        return line in self.changed_lines.get(file_path, set())

    def side_for(self, file_path: str, line: int) -> str | None:
        if self.can_comment(file_path, line):
            return "RIGHT"
        return None
