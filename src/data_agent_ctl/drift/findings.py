# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Drift finding models and helper utilities."""

from __future__ import annotations

from dataclasses import dataclass

from data_agent_ctl.models import FindingSeverity


@dataclass(frozen=True)
class DriftFinding:
    """One drift finding discovered by the drift engine."""

    finding_type: str
    severity: FindingSeverity
    resource: str
    message: str
    remediation_action: str


@dataclass(frozen=True)
class DriftSummary:
    """Aggregated summary over drift findings."""

    total: int
    low: int
    medium: int
    high: int
    critical: int


def summarize(findings: list[DriftFinding]) -> DriftSummary:
    """Summarize findings by severity."""
    by_severity = {
        FindingSeverity.LOW: 0,
        FindingSeverity.MEDIUM: 0,
        FindingSeverity.HIGH: 0,
        FindingSeverity.CRITICAL: 0,
    }
    for finding in findings:
        by_severity[finding.severity] += 1
    return DriftSummary(
        total=len(findings),
        low=by_severity[FindingSeverity.LOW],
        medium=by_severity[FindingSeverity.MEDIUM],
        high=by_severity[FindingSeverity.HIGH],
        critical=by_severity[FindingSeverity.CRITICAL],
    )
