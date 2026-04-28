# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Provider protocol definitions."""
# ruff: noqa: TC001
# pyright: reportReturnType=false

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dagent.models import DataAgentSpec, IAMBinding, RemoteDataAgent


@dataclass(frozen=True)
class ProviderOperationResult:
    """Result model for provider operations."""

    success: bool
    resource: str
    message: str = ""


class DataAgentProvider(Protocol):
    """Provider boundary for remote data-agent lifecycle."""

    def list_agents(self, project_id: str, location: str) -> list[RemoteDataAgent]:
        """List remote data agents for a project/location."""

    def upsert_agent(self, spec: DataAgentSpec) -> ProviderOperationResult:
        """Create or update a remote data agent from desired spec."""

    def disable_agent(self, resource: str) -> ProviderOperationResult:
        """Disable an existing remote data agent."""

    def get_iam_policy(self, resource: str) -> tuple[IAMBinding, ...]:
        """Fetch IAM bindings for a resource."""

    def set_iam_policy(
        self,
        resource: str,
        bindings: tuple[IAMBinding, ...],
    ) -> ProviderOperationResult:
        """Set IAM policy bindings for a resource."""
