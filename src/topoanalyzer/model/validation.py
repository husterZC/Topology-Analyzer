from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "message": self.message,
            "context": dict(self.context),
        }


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, message: str, **context: Any) -> None:
        self.issues.append(ValidationIssue("error", message, context))

    def add_warning(self, message: str, **context: Any) -> None:
        self.issues.append(ValidationIssue("warning", message, context))

    def merge(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_errors(self) -> None:
        if self.errors:
            details = "; ".join(issue.message for issue in self.errors)
            raise ValueError(f"validation failed: {details}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }
