"""dbt source adapter tests."""
# pylint: disable=E1120,E1123

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

from dagent.sources.dbt import DbtSourceAdapter


def test_dbt_adapter_loads_exposure_specs(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    payload = {
        "exposures": {
            "exposure.analytics.agent": {
                "name": "agent-one",
                "description": "Agent description",
                "meta": {
                    "dagent": {
                        "project_id": "analytics-dev",
                        "location": "global",
                        "instructions": "Answer questions.",
                    }
                },
            }
        }
    }
    manifest.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")
    adapter = DbtSourceAdapter(manifest_path=manifest, default_project_id="analytics-dev")
    diagnostics = adapter.validate()
    assert not diagnostics
    specs = adapter.load_specs()
    assert len(specs) == 1
    assert specs[0].project_id == "analytics-dev"
