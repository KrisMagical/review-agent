"""Public issue model for magicreview Phase 1."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["critical", "high", "medium", "low"]
IssueDict = dict[str, Any]


class Issue(BaseModel, Mapping[str, Any]):
    """Stable JSON-serializable issue schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Severity
    type: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line: int = Field(ge=1)
    message: str = Field(min_length=1)
    suggestion: str = Field(default="No suggestion provided.", min_length=1)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower()
        return value

    def to_dict(self) -> IssueDict:
        return self.model_dump()

    def __getitem__(self, key: str) -> Any:
        return self.model_dump()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.model_dump())

    def __len__(self) -> int:
        return len(self.model_dump())

    def get(self, key: str, default: Any = None) -> Any:
        return self.model_dump().get(key, default)


def make_issue(
    *,
    severity: str,
    issue_type: str,
    file_path: str,
    line: int | None,
    message: str,
    suggestion: str,
) -> Issue:
    """Create an issue matching the public JSON schema."""

    return Issue(
        severity=severity,
        type=issue_type,
        file=file_path,
        line=line or 1,
        message=message,
        suggestion=suggestion,
    )


__all__ = ["Issue", "IssueDict", "Severity", "make_issue"]
