# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Plan generation engine."""
# ruff: noqa: TC001,PLR0913,PLR0911

from __future__ import annotations

from datetime import datetime, timezone

from data_agent_ctl.drift.engine import detect_drift
from data_agent_ctl.drift.findings import DriftFinding
from data_agent_ctl.models import DataAgentSpec, RemoteDataAgent
from data_agent_ctl.plan_schema import Plan, PlanAction, PlanMetadata, PlanScope


def build_plan(
    desired_specs: list[DataAgentSpec],
    remote_agents: list[RemoteDataAgent],
    source_name: str,
    projects: list[str],
    location: str,
    source_hash: str = "",
    policy_path: str | None = None,
) -> Plan:
    """Build a reconciliation plan from desired and remote state."""
    findings, _ = detect_drift(desired_specs=desired_specs, remote_agents=remote_agents)
    actions = [
        _finding_to_action(finding=finding, desired_specs=desired_specs) for finding in findings
    ]
    metadata = PlanMetadata(
        source=source_name,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),  # noqa: UP017
        source_hash=source_hash,
        policy_path=policy_path,
    )
    scope = PlanScope(projects=tuple(projects), location=location)
    return Plan(version="2", metadata=metadata, scope=scope, actions=actions)


def _finding_to_action(finding: DriftFinding, desired_specs: list[DataAgentSpec]) -> PlanAction:
    payload = _build_payload(finding=finding, desired_specs=desired_specs)
    destructive = finding.remediation_action == "disable_agent"
    return PlanAction(
        kind=finding.remediation_action,
        resource=finding.resource,
        payload=payload,
        destructive=destructive,
    )


def _build_payload(
    finding: DriftFinding,
    desired_specs: list[DataAgentSpec],
) -> dict[str, str]:
    if finding.remediation_action == "set_iam_policy":
        spec = _find_spec_for_resource(desired_specs=desired_specs, resource=finding.resource)
        if spec is None:
            return {}
        return {"iam_mode": spec.iam_mode.value, "binding_count": str(len(spec.iam_bindings))}
    if finding.remediation_action == "create_agent":
        spec = _find_spec_for_resource(desired_specs=desired_specs, resource=finding.resource)
        if spec is None:
            return {}
        return {"name": spec.name}
    return {}


def _find_spec_for_resource(
    desired_specs: list[DataAgentSpec],
    resource: str,
) -> DataAgentSpec | None:
    for spec in desired_specs:
        key = f"{spec.project_id}/{spec.location}/{spec.name}"
        if key in resource:
            return spec
    return None
