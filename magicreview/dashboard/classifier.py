"""Issue type classification for Dashboard analytics."""

from __future__ import annotations


def classify_issue(issue_type: str) -> str:
    text = issue_type.lower()
    if text.startswith("enterprise"):
        return "enterprise"
    if "fastapi" in text or "pydantic" in text:
        return "fastapi"
    if any(token in text for token in ("sqlinjection", "pathtraversal", "secret", "commandinjection", "jwt", "forbidden")):
        return "security"
    if any(token in text for token in ("none", "keyerror", "index", "zerodivision", "fileleak", "mutabledefault", "deserialization")):
        return "bug"
    if any(token in text for token in ("circular", "coupling", "god", "architecture", "layer", "controller", "boundary")):
        return "architecture"
    if any(token in text for token in ("refactor", "extract", "split", "dto")):
        return "refactor"
    if any(token in text for token in ("functiontoolong", "toomany", "magic", "typehint", "complexity", "maintainability", "ruff")):
        return "quality"
    return "unknown"


def is_bug_type(issue_type: str) -> bool:
    return classify_issue(issue_type) in {"bug", "security"}


def is_technical_debt_type(issue_type: str) -> bool:
    text = issue_type.lower()
    return any(token in text for token in ("functiontoolong", "toomany", "magic", "complexity", "maintainability", "god", "refactor"))


def is_architecture_risk_type(issue_type: str) -> bool:
    return classify_issue(issue_type) == "architecture" or "layer" in issue_type.lower()
