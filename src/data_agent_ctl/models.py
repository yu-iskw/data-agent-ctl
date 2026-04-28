# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Canonical domain models for data-agent-ctl desired/remote state."""
# ruff: noqa: UP042

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IAMMode(str, Enum):
    """IAM reconciliation mode for a data agent."""

    IGNORE = "ignore"
    MEMBER_ADDITIVE = "member_additive"
    AUTHORITATIVE_BINDINGS = "authoritative_bindings"
    AUTHORITATIVE_POLICY = "authoritative_policy"


class FindingSeverity(str, Enum):
    """Severity levels used by drift findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class IAMBinding:
    """Role binding for data-agent IAM policy."""

    role: str
    members: tuple[str, ...]
    condition: str | None = None


@dataclass(frozen=True)
class DataAgentSpec:
    """Provider-neutral desired state for a managed data agent."""

    name: str
    project_id: str
    location: str
    instructions: str
    display_name: str | None = None
    description: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    iam_mode: IAMMode = IAMMode.IGNORE
    iam_bindings: tuple[IAMBinding, ...] = ()
    disabled: bool = False
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteDataAgent:
    """Remote provider representation of a data agent."""

    resource: str
    name: str
    project_id: str
    location: str
    instructions: str
    display_name: str | None = None
    description: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    iam_mode: IAMMode = IAMMode.IGNORE
    iam_bindings: tuple[IAMBinding, ...] = ()
    disabled: bool = False
    provider_fields: dict[str, Any] = field(default_factory=dict)
