# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Typed plan schema for data-agent-ctl plan/apply flow."""
# ruff: noqa: TC003

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PlanAction:
    """A single action entry in a generated plan."""

    kind: str
    resource: str
    payload: dict[str, Any] = field(default_factory=dict)
    destructive: bool = False


@dataclass(frozen=True)
class PlanMetadata:
    """Plan metadata describing source and generation context."""

    source: str
    generated_at: str
    source_hash: str = ""
    policy_path: str | None = None


@dataclass(frozen=True)
class PlanScope:
    """Scope metadata for plan execution."""

    projects: tuple[str, ...] = ()
    location: str = "global"


@dataclass(frozen=True)
class Plan:
    """Serializable plan artifact used by `data-agent-ctl apply`."""

    version: str
    metadata: PlanMetadata
    api_version: str = "data-agent-ctl/v1"
    kind: str = "Plan"
    scope: PlanScope = field(default_factory=PlanScope)
    stale: bool = False
    actions: list[PlanAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the dataclass representation to a JSON-serializable dictionary."""
        return {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "version": self.version,
            "metadata": {
                "source": self.metadata.source,
                "generated_at": self.metadata.generated_at,
                "source_hash": self.metadata.source_hash,
                "policy_path": self.metadata.policy_path,
            },
            "scope": {
                "projects": list(self.scope.projects),
                "location": self.scope.location,
            },
            "stale": self.stale,
            "actions": [
                {
                    "kind": item.kind,
                    "resource": item.resource,
                    "payload": item.payload,
                    "destructive": item.destructive,
                }
                for item in self.actions
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Plan:
        """Parse and validate plan data from a dictionary."""
        if _is_legacy_plan(value):
            return _from_legacy_dict(value)
        required = ("version", "metadata", "actions")
        missing = [key for key in required if key not in value]
        if missing:
            missing_fields = ", ".join(missing)
            raise ValueError(f"Missing required plan field(s): {missing_fields}")
        metadata = _parse_metadata(value["metadata"])
        scope = _parse_scope(value.get("scope", {}))
        actions_raw = value.get("actions", [])
        if not isinstance(actions_raw, list):
            raise TypeError("Plan field 'actions' must be a list.")
        actions = [
            _parse_action(index=index, action_item=action_item)
            for index, action_item in enumerate(actions_raw)
        ]
        return cls(
            api_version=str(value.get("apiVersion", "data-agent-ctl/v1")),
            kind=str(value.get("kind", "Plan")),
            version=str(value["version"]),
            metadata=metadata,
            scope=scope,
            stale=bool(value.get("stale", False)),
            actions=actions,
        )


def load_plan(path: Path) -> Plan:
    """Load and parse a plan artifact from disk."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Plan file is not valid JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise TypeError("Plan file root must be an object.")
    return Plan.from_dict(raw)


def save_plan(path: Path, plan: Plan) -> None:
    """Persist a plan artifact to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(plan.to_dict(), indent=2)}\n", encoding="utf-8")


def _parse_action(index: int, action_item: Any) -> PlanAction:
    if not isinstance(action_item, dict):
        raise TypeError(f"Plan action at index {index} must be an object.")
    if "kind" not in action_item or "resource" not in action_item:
        raise ValueError("Each plan action requires 'kind' and 'resource' fields.")
    payload = action_item.get("payload", {})
    if not isinstance(payload, dict):
        raise TypeError("Plan action field 'payload' must be an object.")
    return PlanAction(
        kind=str(action_item["kind"]),
        resource=str(action_item["resource"]),
        payload=payload,
        destructive=bool(action_item.get("destructive", False)),
    )


def _parse_metadata(raw: Any) -> PlanMetadata:
    if not isinstance(raw, dict):
        raise TypeError("Plan field 'metadata' must be an object.")
    source = str(raw.get("source", "unknown"))
    generated_at = str(raw.get("generated_at", ""))
    source_hash = str(raw.get("source_hash", ""))
    policy_path = raw.get("policy_path")
    if policy_path is not None and not isinstance(policy_path, str):
        raise TypeError("Plan metadata field 'policy_path' must be a string.")
    return PlanMetadata(
        source=source,
        generated_at=generated_at,
        source_hash=source_hash,
        policy_path=policy_path,
    )


def _parse_scope(raw: Any) -> PlanScope:
    if not isinstance(raw, dict):
        raise TypeError("Plan field 'scope' must be an object.")
    projects_raw = raw.get("projects", [])
    if not isinstance(projects_raw, list):
        raise TypeError("Plan scope field 'projects' must be a list.")
    projects = tuple(str(project_id) for project_id in projects_raw)
    location = str(raw.get("location", "global"))
    return PlanScope(projects=projects, location=location)


def _is_legacy_plan(value: dict[str, Any]) -> bool:
    return "source" in value and "generated_at" in value and "metadata" not in value


def _from_legacy_dict(value: dict[str, Any]) -> Plan:
    metadata = PlanMetadata(
        source=str(value["source"]),
        generated_at=str(value["generated_at"]),
    )
    actions_raw = value.get("actions", [])
    if not isinstance(actions_raw, list):
        raise TypeError("Plan field 'actions' must be a list.")
    actions = [
        _parse_legacy_action(index=index, action_item=action_item)
        for index, action_item in enumerate(actions_raw)
    ]
    return Plan(
        version=str(value["version"]),
        metadata=metadata,
        stale=bool(value.get("stale", False)),
        actions=actions,
    )


def _parse_legacy_action(index: int, action_item: Any) -> PlanAction:
    if not isinstance(action_item, dict):
        raise TypeError(f"Plan action at index {index} must be an object.")
    if "action" not in action_item or "resource" not in action_item:
        raise ValueError("Each plan action requires 'action' and 'resource' fields.")
    metadata = action_item.get("metadata", {})
    if not isinstance(metadata, dict):
        raise TypeError("Legacy plan action field 'metadata' must be an object.")
    return PlanAction(
        kind=str(action_item["action"]),
        resource=str(action_item["resource"]),
        payload=metadata,
    )
