# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""dbt manifest source adapter for dagent specs."""
# ruff: noqa: TC003,PLR0911,TRY004
# pylint: disable=E1120,E1123

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dagent.diagnostics import Diagnostic, DiagnosticLevel
from dagent.models import DataAgentSpec, IAMBinding, IAMMode


class DbtSourceAdapter:
    """Load desired data-agent specs from a dbt manifest."""

    source_name = "dbt"

    def __init__(
        self,
        manifest_path: Path,
        default_project_id: str,
        default_location: str = "global",
    ) -> None:
        self._manifest_path = manifest_path
        self._default_project_id = default_project_id
        self._default_location = default_location

    def validate(self) -> list[Diagnostic]:
        """Validate the dbt manifest and required exposure metadata."""
        path = self._manifest_path
        if not path.exists():
            return [
                Diagnostic(
                    code="dbt.file_missing",
                    message=f"Manifest file does not exist: {path}",
                    level=DiagnosticLevel.ERROR,
                    path=str(path),
                )
            ]
        try:
            raw = _load_manifest(path=path)
        except ValueError as exc:
            return [
                Diagnostic(
                    code="dbt.parse_error",
                    message=str(exc),
                    level=DiagnosticLevel.ERROR,
                    path=str(path),
                )
            ]
        exposures = _extract_exposures(raw=raw)
        if not exposures:
            return [
                Diagnostic(
                    code="dbt.no_exposures",
                    message="Manifest has no exposures to convert into data-agent specs.",
                    level=DiagnosticLevel.WARNING,
                    path=str(path),
                )
            ]
        diagnostics: list[Diagnostic] = []
        for exposure_name, exposure in exposures:
            meta = exposure.get("meta", {})
            instructions = meta.get("dagent_instructions") or exposure.get("description")
            if not instructions:
                diagnostics.append(
                    Diagnostic(
                        code="dbt.missing_instructions",
                        message=(
                            f"Exposure missing dagent instructions (exposure: {exposure_name})."
                        ),
                        level=DiagnosticLevel.ERROR,
                        path=str(path),
                    )
                )
        return diagnostics

    def load_specs(self) -> list[DataAgentSpec]:
        """Convert dbt exposures in manifest to canonical data-agent specs."""
        raw = _load_manifest(path=self._manifest_path)
        specs: list[DataAgentSpec] = []
        for exposure_name, exposure in _extract_exposures(raw=raw):
            specs.append(
                _to_spec(
                    exposure_name=exposure_name,
                    exposure=exposure,
                    default_project_id=self._default_project_id,
                    default_location=self._default_location,
                    manifest_path=self._manifest_path,
                )
            )
        return specs


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Manifest root must be a JSON object.")
    return raw


def _extract_exposures(raw: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    exposures_raw = raw.get("exposures", {})
    if not isinstance(exposures_raw, dict):
        return []
    entries: list[tuple[str, dict[str, Any]]] = []
    for unique_id, value in exposures_raw.items():
        if isinstance(value, dict):
            exposure_name = str(value.get("name", unique_id))
            entries.append((exposure_name, value))
    return entries


def _to_spec(
    exposure_name: str,
    exposure: dict[str, Any],
    default_project_id: str,
    default_location: str,
    manifest_path: Path,
) -> DataAgentSpec:
    meta = exposure.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    dagent_meta = meta.get("dagent", {})
    if not isinstance(dagent_meta, dict):
        dagent_meta = {}

    instructions = (
        dagent_meta.get("instructions")
        or meta.get("dagent_instructions")
        or exposure.get("description")
        or f"Answer questions for exposure {exposure_name}."
    )
    tags = tuple(str(tag) for tag in exposure.get("tags", []))
    labels = _labels_from_meta(meta=meta)
    iam_mode = _parse_iam_mode(dagent_meta.get("iam_mode", IAMMode.IGNORE.value))
    iam_bindings = _parse_iam_bindings(dagent_meta.get("iam_bindings", []))
    return DataAgentSpec(
        name=str(dagent_meta.get("name", exposure_name)),
        project_id=str(dagent_meta.get("project_id", default_project_id)),
        location=str(dagent_meta.get("location", default_location)),
        instructions=str(instructions),
        display_name=_opt_text(dagent_meta.get("display_name", exposure.get("label"))),
        description=_opt_text(exposure.get("description")),
        labels=labels,
        tags=tags,
        iam_mode=iam_mode,
        iam_bindings=iam_bindings,
        disabled=bool(dagent_meta.get("disabled", False)),
        source_metadata={
            "manifest_path": str(manifest_path),
            "dbt_exposure_name": exposure_name,
            "depends_on": tuple(exposure.get("depends_on", {}).get("nodes", [])),
        },
    )


def _opt_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _labels_from_meta(meta: dict[str, Any]) -> dict[str, str]:
    labels = meta.get("labels", {})
    if not isinstance(labels, dict):
        labels = {}
    return {str(key): str(value) for key, value in labels.items()}


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
        condition_raw = item.get("condition")
        condition = str(condition_raw) if isinstance(condition_raw, str) else None
        bindings.append(IAMBinding(role=role, members=members, condition=condition))
    return tuple(bindings)
