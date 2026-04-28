# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Inventory collection and export helpers."""
# ruff: noqa: TC001,TC003

from __future__ import annotations

import csv
import json
from pathlib import Path

from data_agent_ctl.providers.base import DataAgentProvider


def collect_inventory(
    provider: DataAgentProvider,
    projects: list[str],
    location: str,
) -> list[dict[str, str]]:
    """Collect normalized remote inventory rows for projects and location."""
    rows: list[dict[str, str]] = []
    for project_id in projects:
        agents = provider.list_agents(project_id=project_id, location=location)
        rows.extend(
            [
                {
                    "project_id": project_id,
                    "location": location,
                    "resource": agent.resource,
                    "name": agent.name,
                    "disabled": str(agent.disabled).lower(),
                }
                for agent in agents
            ]
        )
    return rows


def write_inventory(
    rows: list[dict[str, str]],
    output_path: Path,
    output_format: str,
) -> None:
    """Write inventory rows as CSV or JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "csv":
        _write_csv(rows=rows, output_path=output_path)
        return
    output_path.write_text(f"{json.dumps(rows, indent=2)}\n", encoding="utf-8")


def _write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = ["project_id", "location", "resource", "name", "disabled"]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
