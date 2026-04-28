"""Drift engine tests."""
# pylint: disable=E1120,E1123

from __future__ import annotations

from dagent.drift.engine import detect_drift
from dagent.models import DataAgentSpec, RemoteDataAgent


def test_detect_drift_reports_missing_remote_agent() -> None:
    desired = [
        DataAgentSpec(
            name="agent-one",
            project_id="analytics-dev",
            location="global",
            instructions="Answer questions.",
        )
    ]
    findings, summary = detect_drift(desired_specs=desired, remote_agents=[])
    assert findings
    assert summary.high >= 1
    assert findings[0].finding_type == "missing_remote_agent"


def test_detect_drift_reports_instruction_change() -> None:
    desired = [
        DataAgentSpec(
            name="agent-one",
            project_id="analytics-dev",
            location="global",
            instructions="new instructions",
        )
    ]
    remote = [
        RemoteDataAgent(
            resource="projects/analytics-dev/locations/global/dataAgents/agent-one",
            name="agent-one",
            project_id="analytics-dev",
            location="global",
            instructions="old instructions",
        )
    ]
    findings, _ = detect_drift(desired_specs=desired, remote_agents=remote)
    assert any(item.finding_type == "instructions_drift" for item in findings)
