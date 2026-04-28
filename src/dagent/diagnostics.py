# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Diagnostics primitives shared by validation and source adapters."""
# ruff: noqa: TC003,UP042

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class DiagnosticLevel(str, Enum):
    """Severity level for diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


DiagnosticSeverity = DiagnosticLevel


@dataclass(frozen=True)
class Diagnostic:
    """A single validation or parsing diagnostic."""

    code: str
    message: str
    level: DiagnosticLevel = DiagnosticLevel.ERROR
    path: str | None = None
    location: str | None = None
    context: dict[str, str] | None = None

    @property
    def severity(self) -> DiagnosticLevel:
        """Backward-compatible alias used by older adapters/tests."""
        return self.level


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    """Return true when at least one diagnostic has error level."""
    return any(item.level is DiagnosticLevel.ERROR for item in diagnostics)
