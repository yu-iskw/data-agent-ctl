# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0

"""Plan schema tests."""
# pylint: disable=E1120,E1123

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

import pytest

from dagent.plan_schema import Plan, PlanAction, PlanMetadata, PlanScope, load_plan, save_plan


def test_plan_roundtrip_v2(tmp_path: Path) -> None:
    plan = Plan(
        version="2",
        metadata=PlanMetadata(source="dbt", generated_at="2026-04-28T00:00:00+00:00"),
        scope=PlanScope(projects=("analytics-dev",), location="global"),
        actions=[
            PlanAction(
                kind="create_agent", resource="projects/analytics-dev/locations/global/dataAgents/a"
            )
        ],
    )
    path = tmp_path / "plan.json"
    save_plan(path=path, plan=plan)
    loaded = load_plan(path)
    assert loaded.version == "2"
    assert loaded.metadata.source == "dbt"
    assert loaded.actions[0].kind == "create_agent"


def test_load_legacy_plan_is_compatible(tmp_path: Path) -> None:
    path = tmp_path / "legacy.json"
    payload = {
        "version": "1",
        "source": "dbt",
        "generated_at": "2026-04-28T00:00:00+00:00",
        "actions": [
            {"action": "sync_agents", "resource": "projects/analytics-dev", "metadata": {}}
        ],
    }
    path.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")
    loaded = load_plan(path)
    assert loaded.metadata.source == "dbt"
    assert loaded.actions[0].kind == "sync_agents"


def test_invalid_actions_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {"version": "2", "metadata": {"source": "dbt", "generated_at": "x"}, "actions": {}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(TypeError):
        _ = load_plan(path)
