"""Inventory export tests."""
# pylint: disable=E1120,E1123

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from data_agent_ctl.inventory import collect_inventory, write_inventory
from data_agent_ctl.models import DataAgentSpec
from data_agent_ctl.providers.google_gemini_data_analytics import (
    GoogleGeminiDataAnalyticsProvider,
    InMemoryProviderTransport,
)


def test_inventory_export_csv(tmp_path: Path) -> None:
    provider = GoogleGeminiDataAnalyticsProvider(transport=InMemoryProviderTransport())
    _ = provider.upsert_agent(
        DataAgentSpec(
            name="agent-one",
            project_id="analytics-dev",
            location="global",
            instructions="Answer questions.",
        )
    )
    rows = collect_inventory(provider=provider, projects=["analytics-dev"], location="global")
    output = tmp_path / "inventory.csv"
    write_inventory(rows=rows, output_path=output, output_format="csv")
    assert output.exists()
    assert "agent-one" in output.read_text(encoding="utf-8")
