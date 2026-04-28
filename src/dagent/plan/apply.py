# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Plan apply orchestration."""
# ruff: noqa: TC001,PLR0911

from __future__ import annotations

from dataclasses import dataclass

from dagent.models import DataAgentSpec
from dagent.plan_schema import Plan, PlanAction
from dagent.providers.base import DataAgentProvider


@dataclass(frozen=True)
class ApplyResult:
    """Apply result summary."""

    succeeded: int
    failed: int
    failures: tuple[str, ...]


def apply_plan(
    plan: Plan,
    provider: DataAgentProvider,
    desired_specs: list[DataAgentSpec],
) -> ApplyResult:
    """Apply plan actions using provider operations."""
    succeeded = 0
    failed = 0
    failures: list[str] = []
    for action in plan.actions:
        if _apply_action(action=action, provider=provider, desired_specs=desired_specs):
            succeeded += 1
        else:
            failed += 1
            failures.append(action.resource)
    return ApplyResult(succeeded=succeeded, failed=failed, failures=tuple(failures))


def _apply_action(
    action: PlanAction,
    provider: DataAgentProvider,
    desired_specs: list[DataAgentSpec],
) -> bool:
    kind = action.kind
    if kind == "disable_agent":
        result = provider.disable_agent(resource=action.resource)
        return result.success
    if kind == "set_iam_policy":
        spec = _find_spec_for_resource(desired_specs=desired_specs, resource=action.resource)
        if spec is None:
            return False
        result = provider.set_iam_policy(resource=action.resource, bindings=spec.iam_bindings)
        return result.success
    if kind in {"create_agent", "update_agent"}:
        spec = _find_spec_for_resource(desired_specs=desired_specs, resource=action.resource)
        if spec is None:
            return False
        result = provider.upsert_agent(spec=spec)
        return result.success
    return True


def _find_spec_for_resource(
    desired_specs: list[DataAgentSpec],
    resource: str,
) -> DataAgentSpec | None:
    for spec in desired_specs:
        key = f"{spec.project_id}/{spec.location}/{spec.name}"
        if key in resource:
            return spec
    return None
