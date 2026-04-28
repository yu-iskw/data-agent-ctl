# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""State-based tests for data-agent-ctl CLI contract and safety gates."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

import pytest

from data_agent_ctl.cli import main
from data_agent_ctl.exit_codes import ExitCode


def _write_manifest(path: Path) -> None:
    payload = {
        "metadata": {"generated_at": "2026-04-28T00:00:00Z"},
        "exposures": {
            "exposure.analytics.sales_agent": {
                "name": "sales-agent",
                "description": "Answer sales questions.",
                "tags": ["sales"],
                "meta": {
                    "data-agent-ctl": {
                        "project_id": "analytics-dev",
                        "location": "global",
                        "instructions": "Answer governed sales questions.",
                    },
                    "labels": {"team": "analytics"},
                },
            }
        },
    }
    path.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")


def test_help_includes_examples(capsys: pytest.CaptureFixture[str]) -> None:
    """Top-level help must be discoverable with concrete examples."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Examples:" in output
    assert "data-agent-ctl apply target/data-agent-ctl.plan.json --yes" in output


def test_validate_requires_existing_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Validate fails fast with actionable remediation when input is missing."""
    missing_manifest = tmp_path / "manifest.json"
    code = main(["validate", "--source", "dbt", "--manifest", str(missing_manifest)])
    assert code == ExitCode.VALIDATION_FAILED
    stderr = capsys.readouterr().err
    assert "manifest file does not exist" in stderr
    assert "manifest file does not exist" in stderr


def test_plan_writes_artifact_and_apply_succeeds(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Plan and apply complete through an in-process artifact handoff."""
    manifest = tmp_path / "manifest.json"
    out_plan = tmp_path / "data-agent-ctl.plan.json"
    _write_manifest(manifest)

    code = main(
        [
            "plan",
            "--source",
            "dbt",
            "--manifest",
            str(manifest),
            "--projects",
            "analytics-dev",
            "--location",
            "global",
            "--out",
            str(out_plan),
        ]
    )
    assert code == ExitCode.SUCCESS
    stdout = capsys.readouterr().out
    assert "plan.generated" in stdout
    assert out_plan.exists()

    plan_payload = json.loads(out_plan.read_text(encoding="utf-8"))
    assert plan_payload["metadata"]["source"] == "dbt"
    assert "scope" in plan_payload

    apply_code = main(["apply", str(out_plan), "--yes"])
    assert apply_code == ExitCode.SUCCESS
    apply_stdout = capsys.readouterr().out
    assert "apply.simulated" in apply_stdout


def test_apply_requires_yes_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Apply blocks without explicit non-interactive confirmation."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": "1",
                "metadata": {"source": "dbt", "generated_at": "2026-04-28T00:00:00+00:00"},
                "stale": False,
                "actions": [],
            }
        ),
        encoding="utf-8",
    )

    code = main(["apply", str(plan_path)])
    assert code == ExitCode.FORBIDDEN_ACTION
    assert "apply requires explicit confirmation flag" in capsys.readouterr().err


def test_apply_rejects_stale_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stale plans fail closed before apply side effects."""
    plan_path = tmp_path / "stale.plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": "1",
                "metadata": {"source": "dbt", "generated_at": "2026-04-28T00:00:00+00:00"},
                "stale": True,
                "actions": [],
            }
        ),
        encoding="utf-8",
    )

    code = main(["apply", str(plan_path), "--yes"])
    assert code == ExitCode.STALE_PLAN
    assert "policy_violation=stale_plan" in capsys.readouterr().err


def test_apply_rejects_forbidden_policy_action(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Forbidden actions fail with policy-oriented diagnostics."""
    plan_path = tmp_path / "forbidden.plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": "1",
                "metadata": {"source": "dbt", "generated_at": "2026-04-28T00:00:00+00:00"},
                "stale": False,
                "actions": [
                    {
                        "kind": "grant_public_iam",
                        "resource": "projects/analytics-dev",
                        "payload": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    code = main(["apply", str(plan_path), "--yes"])
    assert code == ExitCode.FORBIDDEN_ACTION
    assert "policy_violation=forbidden_action" in capsys.readouterr().err


def test_drift_detect_exit_code_when_high_findings(
    tmp_path: Path,
) -> None:
    """Drift detect exits with DRIFT_DETECTED when threshold is exceeded."""
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)
    code = main(
        [
            "drift",
            "detect",
            "--source",
            "dbt",
            "--manifest",
            str(manifest),
            "--projects",
            "analytics-dev",
            "--location",
            "global",
            "--fail-on",
            "high",
        ]
    )
    assert code == ExitCode.DRIFT_DETECTED


def test_inventory_export_writes_json(tmp_path: Path) -> None:
    """Inventory export writes output file in requested format."""
    output = tmp_path / "inventory.json"
    code = main(
        [
            "inventory",
            "export",
            "--projects",
            "analytics-dev",
            "--location",
            "global",
            "--format",
            "json",
            "--out",
            str(output),
        ]
    )
    assert code == ExitCode.SUCCESS
    assert output.exists()
