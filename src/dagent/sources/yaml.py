# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""YAML source adapter for dagent specs."""
# ruff: noqa: TC003,PERF401,PLR0911
# pylint: disable=E1120,E1123

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dagent.diagnostics import Diagnostic, DiagnosticLevel
from dagent.models import DataAgentSpec, IAMBinding, IAMMode


class YamlSourceAdapter:
    """Load desired data-agent specs from YAML files."""

    source_name = "yaml"

    def __init__(
        self,
        spec_paths: list[Path],
        default_project_id: str,
        default_location: str = "global",
    ) -> None:
        self._spec_paths = spec_paths
        self._default_project_id = default_project_id
        self._default_location = default_location

    def validate(self) -> list[Diagnostic]:
        """Validate YAML source files and required top-level fields."""
        diagnostics: list[Diagnostic] = []
        for path in self._spec_paths:
            if not path.exists():
                diagnostics.append(
                    Diagnostic(
                        code="yaml.file_missing",
                        message=f"Spec file does not exist: {path}",
                        level=DiagnosticLevel.ERROR,
                        path=str(path),
                    )
                )
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                diagnostics.append(
                    Diagnostic(
                        code="yaml.parse_error",
                        message=f"Invalid YAML: {exc}",
                        level=DiagnosticLevel.ERROR,
                        path=str(path),
                    )
                )
                continue
            diagnostics.extend(_validate_yaml_payload(raw=raw, path=path))
        return diagnostics

    def load_specs(self) -> list[DataAgentSpec]:
        """Load and convert YAML documents to canonical data-agent specs."""
        specs: list[DataAgentSpec] = []
        for path in self._spec_paths:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            for spec_raw in _expand_spec_docs(raw):
                specs.append(
                    _to_data_agent_spec(
                        spec_raw=spec_raw,
                        default_project_id=self._default_project_id,
                        default_location=self._default_location,
                        source_metadata={"source_path": str(path)},
                    )
                )
        return specs


def _expand_spec_docs(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        if "data_agents" in raw and isinstance(raw["data_agents"], list):
            return [item for item in raw["data_agents"] if isinstance(item, dict)]
        return [raw]
    return []


def _validate_yaml_payload(raw: Any, path: Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    docs = _expand_spec_docs(raw=raw)
    if not docs:
        diagnostics.append(
            Diagnostic(
                code="yaml.empty_specs",
                message="No data-agent specs found in YAML file.",
                level=DiagnosticLevel.ERROR,
                path=str(path),
            )
        )
        return diagnostics
    for index, item in enumerate(docs):
        if "name" not in item:
            diagnostics.append(
                Diagnostic(
                    code="yaml.missing_name",
                    message=f"Missing required field 'name' at index {index}.",
                    level=DiagnosticLevel.ERROR,
                    path=str(path),
                )
            )
        if "instructions" not in item:
            diagnostics.append(
                Diagnostic(
                    code="yaml.missing_instructions",
                    message=f"Missing required field 'instructions' at index {index}.",
                    level=DiagnosticLevel.ERROR,
                    path=str(path),
                )
            )
    return diagnostics


def _to_data_agent_spec(
    spec_raw: dict[str, Any],
    default_project_id: str,
    default_location: str,
    source_metadata: dict[str, Any],
) -> DataAgentSpec:
    name = str(spec_raw["name"])
    instructions = str(spec_raw["instructions"])
    project_id = str(spec_raw.get("project_id", default_project_id))
    location = str(spec_raw.get("location", default_location))
    tags = tuple(str(tag) for tag in spec_raw.get("tags", []))
    labels = _parse_labels(spec_raw.get("labels", {}))
    iam_mode = _parse_iam_mode(spec_raw.get("iam_mode", IAMMode.IGNORE.value))
    iam_bindings = _parse_iam_bindings(spec_raw.get("iam_bindings", []))
    return DataAgentSpec(
        name=name,
        project_id=project_id,
        location=location,
        instructions=instructions,
        display_name=_parse_optional_text(spec_raw.get("display_name")),
        description=_parse_optional_text(spec_raw.get("description")),
        labels=labels,
        tags=tags,
        iam_mode=iam_mode,
        iam_bindings=iam_bindings,
        disabled=bool(spec_raw.get("disabled", False)),
        source_metadata=source_metadata,
    )


def _parse_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_labels(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(label_value) for key, label_value in value.items()}


def _parse_iam_mode(value: Any) -> IAMMode:
    try:
        return IAMMode(str(value))
    except ValueError:
        return IAMMode.IGNORE


def _parse_iam_bindings(value: Any) -> tuple[IAMBinding, ...]:
    if not isinstance(value, list):
        return ()
    bindings: list[IAMBinding] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        members_raw = item.get("members", [])
        members = tuple(str(member) for member in members_raw if isinstance(member, str))
        if not role:
            continue
        condition = item.get("condition")
        bindings.append(
            IAMBinding(
                role=role,
                members=members,
                condition=str(condition) if isinstance(condition, str) else None,
            )
        )
    return tuple(bindings)
