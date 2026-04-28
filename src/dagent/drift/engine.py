# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Drift detection engine."""

from __future__ import annotations

from dagent.canonicalize import canonicalize_spec
from dagent.drift.findings import DriftFinding, DriftSummary, summarize
from dagent.models import DataAgentSpec, FindingSeverity, RemoteDataAgent


def detect_drift(
    desired_specs: list[DataAgentSpec],
    remote_agents: list[RemoteDataAgent],
) -> tuple[list[DriftFinding], DriftSummary]:
    """Compare desired and remote state and produce drift findings."""
    desired_by_key = {_spec_key(spec): canonicalize_spec(spec) for spec in desired_specs}
    remote_by_key = {_remote_key(remote): remote for remote in remote_agents}
    findings: list[DriftFinding] = []
    findings.extend(
        _find_missing_agents(desired_by_key=desired_by_key, remote_by_key=remote_by_key)
    )
    findings.extend(
        _find_unmanaged_agents(desired_by_key=desired_by_key, remote_by_key=remote_by_key)
    )
    findings.extend(
        _find_changed_agents(desired_by_key=desired_by_key, remote_by_key=remote_by_key)
    )
    return findings, summarize(findings=findings)


def _spec_key(spec: DataAgentSpec) -> str:
    return f"{spec.project_id}/{spec.location}/{spec.name}"


def _remote_key(remote: RemoteDataAgent) -> str:
    return f"{remote.project_id}/{remote.location}/{remote.name}"


def _find_missing_agents(
    desired_by_key: dict[str, DataAgentSpec],
    remote_by_key: dict[str, RemoteDataAgent],
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for key, desired in desired_by_key.items():
        if key not in remote_by_key:
            findings.append(
                DriftFinding(
                    finding_type="missing_remote_agent",
                    severity=FindingSeverity.HIGH,
                    resource=key,
                    message=f"Agent '{desired.name}' is missing remotely.",
                    remediation_action="create_agent",
                )
            )
    return findings


def _find_unmanaged_agents(
    desired_by_key: dict[str, DataAgentSpec],
    remote_by_key: dict[str, RemoteDataAgent],
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for key, remote in remote_by_key.items():
        if key not in desired_by_key:
            findings.append(
                DriftFinding(
                    finding_type="unmanaged_remote_agent",
                    severity=FindingSeverity.MEDIUM,
                    resource=remote.resource or key,
                    message=f"Remote agent '{remote.name}' has no desired spec.",
                    remediation_action="disable_agent",
                )
            )
    return findings


def _find_changed_agents(
    desired_by_key: dict[str, DataAgentSpec],
    remote_by_key: dict[str, RemoteDataAgent],
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for key, desired in desired_by_key.items():
        remote = remote_by_key.get(key)
        if remote is None:
            continue
        findings.extend(_compare_agent(desired=desired, remote=remote, key=key))
    return findings


def _compare_agent(
    desired: DataAgentSpec,
    remote: RemoteDataAgent,
    key: str,
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    if desired.instructions.strip() != remote.instructions.strip():
        findings.append(
            DriftFinding(
                finding_type="instructions_drift",
                severity=FindingSeverity.HIGH,
                resource=remote.resource or key,
                message="Agent instructions differ from desired state.",
                remediation_action="update_agent",
            )
        )
    if desired.labels != remote.labels:
        findings.append(
            DriftFinding(
                finding_type="labels_drift",
                severity=FindingSeverity.MEDIUM,
                resource=remote.resource or key,
                message="Agent labels differ from desired state.",
                remediation_action="update_agent",
            )
        )
    if desired.iam_bindings != remote.iam_bindings:
        findings.append(
            DriftFinding(
                finding_type="iam_drift",
                severity=FindingSeverity.HIGH,
                resource=remote.resource or key,
                message="Agent IAM bindings differ from desired state.",
                remediation_action="set_iam_policy",
            )
        )
    if desired.disabled != remote.disabled:
        findings.append(
            DriftFinding(
                finding_type="disabled_state_drift",
                severity=FindingSeverity.MEDIUM,
                resource=remote.resource or key,
                message="Agent disabled flag differs from desired state.",
                remediation_action="update_agent",
            )
        )
    return findings
