"""YAML source adapter tests."""
# pylint: disable=E1120,E1123

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from data_agent_ctl.sources.yaml import YamlSourceAdapter


def test_yaml_adapter_loads_specs(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agents.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "data_agents:",
                "  - name: agent-one",
                "    project_id: analytics-dev",
                "    location: global",
                "    instructions: answer questions",
            ]
        ),
        encoding="utf-8",
    )
    adapter = YamlSourceAdapter(
        spec_paths=[yaml_path],
        default_project_id="analytics-dev",
        default_location="global",
    )
    diagnostics = adapter.validate()
    assert not diagnostics
    specs = adapter.load_specs()
    assert len(specs) == 1
    assert specs[0].name == "agent-one"
