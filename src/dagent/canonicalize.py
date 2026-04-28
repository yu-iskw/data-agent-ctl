# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Canonicalization helpers for stable planning and drift comparisons."""
# pylint: disable=E1120,E1123

from __future__ import annotations

from dagent.models import DataAgentSpec, IAMBinding


def canonicalize_spec(spec: DataAgentSpec) -> DataAgentSpec:
    """Return a canonicalized data-agent spec for deterministic comparison."""
    return DataAgentSpec(
        name=spec.name.strip(),
        project_id=spec.project_id.strip(),
        location=spec.location.strip() or "global",
        instructions=_normalize_instructions(spec.instructions),
        display_name=_normalize_optional_text(spec.display_name),
        description=_normalize_optional_text(spec.description),
        labels=_canonicalize_labels(spec.labels),
        tags=_canonicalize_tags(spec.tags),
        iam_mode=spec.iam_mode,
        iam_bindings=_canonicalize_bindings(spec.iam_bindings),
        disabled=spec.disabled,
        source_metadata=spec.source_metadata,
    )


def _normalize_instructions(instructions: str) -> str:
    normalized_newlines = instructions.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized_newlines.split("\n")).strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _canonicalize_labels(labels: dict[str, str]) -> dict[str, str]:
    return {key: labels[key] for key in sorted(labels.keys())}


def _canonicalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(tag.strip() for tag in tags))


def _canonicalize_bindings(bindings: tuple[IAMBinding, ...]) -> tuple[IAMBinding, ...]:
    normalized = [
        IAMBinding(
            role=binding.role,
            members=tuple(sorted({member.strip() for member in binding.members})),
            condition=binding.condition.strip() if isinstance(binding.condition, str) else None,
        )
        for binding in bindings
    ]
    return tuple(sorted(normalized, key=lambda binding: (binding.role, binding.condition or "")))
