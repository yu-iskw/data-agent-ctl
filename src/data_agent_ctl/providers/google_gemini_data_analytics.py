# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Google Gemini Data Analytics provider with transport seam."""
# ruff: noqa: PLR0911
# pyright: reportReturnType=false

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from data_agent_ctl.models import DataAgentSpec, IAMBinding, IAMMode, RemoteDataAgent
from data_agent_ctl.providers.base import ProviderOperationResult


class ProviderTransport(Protocol):
    """Low-level provider transport boundary."""

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute one provider request and return response payload."""


@dataclass
class InMemoryProviderTransport:
    """Deterministic in-memory transport for tests and local workflows."""

    agents: dict[str, dict[str, Any]] = field(default_factory=dict)
    iam_policies: dict[str, tuple[IAMBinding, ...]] = field(default_factory=dict)

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method == "GET" and path.endswith("/dataAgents"):
            prefix = path.removesuffix("/dataAgents")
            agents = [
                value for resource, value in self.agents.items() if resource.startswith(prefix)
            ]
            return {"data_agents": agents}
        if method == "PUT":
            self.agents[path] = payload or {}
            return {"resource": path}
        if method == "PATCH":
            original = self.agents.get(path, {})
            original.update(payload or {})
            self.agents[path] = original
            return {"resource": path}
        if method == "GET" and path.endswith(":getIamPolicy"):
            resource = path.removesuffix(":getIamPolicy")
            bindings = self.iam_policies.get(resource, ())
            return {"bindings": [binding.__dict__ for binding in bindings]}
        if method == "POST" and path.endswith(":setIamPolicy"):
            resource = path.removesuffix(":setIamPolicy")
            bindings = _bindings_from_payload(payload or {})
            self.iam_policies[resource] = bindings
            return {"resource": resource}
        return {}


class GoogleGeminiDataAnalyticsProvider:
    """Provider implementation translating between models and API payloads."""

    def __init__(self, transport: ProviderTransport | None = None) -> None:
        self._transport = transport or InMemoryProviderTransport()

    def list_agents(self, project_id: str, location: str) -> list[RemoteDataAgent]:
        parent = _project_location_path(project_id=project_id, location=location)
        response = self._transport.request(method="GET", path=f"{parent}/dataAgents")
        agents = response.get("data_agents", [])
        if not isinstance(agents, list):
            return []
        return [_remote_agent_from_payload(item) for item in agents if isinstance(item, dict)]

    def upsert_agent(self, spec: DataAgentSpec) -> ProviderOperationResult:
        resource = _agent_resource(
            project_id=spec.project_id, location=spec.location, name=spec.name
        )
        self._transport.request(method="PUT", path=resource, payload=_payload_from_spec(spec=spec))
        return ProviderOperationResult(success=True, resource=resource, message="upserted")

    def disable_agent(self, resource: str) -> ProviderOperationResult:
        self._transport.request(method="PATCH", path=resource, payload={"disabled": True})
        return ProviderOperationResult(success=True, resource=resource, message="disabled")

    def get_iam_policy(self, resource: str) -> tuple[IAMBinding, ...]:
        response = self._transport.request(method="GET", path=f"{resource}:getIamPolicy")
        return _bindings_from_payload(response)

    def set_iam_policy(
        self,
        resource: str,
        bindings: tuple[IAMBinding, ...],
    ) -> ProviderOperationResult:
        payload = {"bindings": [binding.__dict__ for binding in bindings]}
        self._transport.request(method="POST", path=f"{resource}:setIamPolicy", payload=payload)
        return ProviderOperationResult(success=True, resource=resource, message="iam_updated")


def _project_location_path(project_id: str, location: str) -> str:
    return f"projects/{project_id}/locations/{location}"


def _agent_resource(project_id: str, location: str, name: str) -> str:
    return f"{_project_location_path(project_id=project_id, location=location)}/dataAgents/{name}"


def _payload_from_spec(spec: DataAgentSpec) -> dict[str, Any]:
    return {
        "resource": _agent_resource(
            project_id=spec.project_id, location=spec.location, name=spec.name
        ),
        "name": spec.name,
        "project_id": spec.project_id,
        "location": spec.location,
        "instructions": spec.instructions,
        "display_name": spec.display_name,
        "description": spec.description,
        "labels": spec.labels,
        "tags": list(spec.tags),
        "iam_mode": spec.iam_mode.value,
        "iam_bindings": [binding.__dict__ for binding in spec.iam_bindings],
        "disabled": spec.disabled,
    }


def _remote_agent_from_payload(payload: dict[str, Any]) -> RemoteDataAgent:
    return RemoteDataAgent(
        resource=str(payload.get("resource", "")),
        name=str(payload.get("name", "")),
        project_id=str(payload.get("project_id", "")),
        location=str(payload.get("location", "global")),
        instructions=str(payload.get("instructions", "")),
        display_name=_opt_text(payload.get("display_name")),
        description=_opt_text(payload.get("description")),
        labels=_parse_labels(payload.get("labels", {})),
        tags=tuple(str(tag) for tag in payload.get("tags", [])),
        iam_mode=_parse_iam_mode(payload.get("iam_mode", "ignore")),
        iam_bindings=_bindings_from_payload(payload),
        disabled=bool(payload.get("disabled", False)),
    )


def _bindings_from_payload(payload: dict[str, Any]) -> tuple[IAMBinding, ...]:
    bindings_raw = payload.get("bindings", payload.get("iam_bindings", []))
    if not isinstance(bindings_raw, list):
        return ()
    bindings: list[IAMBinding] = []
    for item in bindings_raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        members_raw = item.get("members", [])
        members = tuple(str(member) for member in members_raw if isinstance(member, str))
        if not role:
            continue
        condition_raw = item.get("condition")
        condition = str(condition_raw) if isinstance(condition_raw, str) else None
        bindings.append(IAMBinding(role=role, members=members, condition=condition))
    return tuple(bindings)


def _opt_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_labels(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _parse_iam_mode(value: Any) -> IAMMode:
    try:
        return IAMMode(str(value))
    except ValueError:
        return IAMMode.IGNORE
