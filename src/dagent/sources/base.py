# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Source adapter protocol definitions."""
# ruff: noqa: TC001,TC003
# pyright: reportReturnType=false

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from dagent.diagnostics import Diagnostic
from dagent.models import DataAgentSpec


class SourceAdapter(Protocol):
    """Loads desired specs from source artifacts."""

    source_name: str

    def load_specs(self) -> list[DataAgentSpec]:
        """Load desired specs from source artifacts."""

    def validate(self) -> list[Diagnostic]:
        """Validate source artifacts and return diagnostics."""


def read_text(path: Path) -> str:
    """Read UTF-8 text from a file path."""
    return path.read_text(encoding="utf-8")
