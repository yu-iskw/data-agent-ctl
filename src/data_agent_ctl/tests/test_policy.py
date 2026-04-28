# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Policy gate tests."""
# pylint: disable=E1120,E1123

from __future__ import annotations

from data_agent_ctl.models import DataAgentSpec, IAMBinding, IAMMode
from data_agent_ctl.plan_schema import Plan, PlanAction, PlanMetadata
from data_agent_ctl.policy import PolicyConfig, evaluate_plan, evaluate_specs


def test_plan_policy_blocks_destructive_without_allow_delete() -> None:
    plan = Plan(
        version="2",
        metadata=PlanMetadata(source="dbt", generated_at="2026-04-28T00:00:00+00:00"),
        actions=[PlanAction(kind="disable_agent", resource="x", destructive=True)],
    )
    result = evaluate_plan(plan=plan, allow_delete=False)
    assert not result.allowed
    assert any(item.code == "delete_not_allowed" for item in result.violations)


def test_spec_policy_blocks_public_member() -> None:
    spec = DataAgentSpec(
        name="agent",
        project_id="analytics-dev",
        location="global",
        instructions="help",
        iam_mode=IAMMode.MEMBER_ADDITIVE,
        iam_bindings=(IAMBinding(role="roles/viewer", members=("allUsers",)),),
    )
    result = evaluate_specs(specs=[spec], policy_config=PolicyConfig(allow_public_members=False))
    assert not result.allowed
    assert any(item.code == "public_member_forbidden" for item in result.violations)
