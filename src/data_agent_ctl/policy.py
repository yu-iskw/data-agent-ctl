# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Safety policy evaluation for plan apply decisions."""
# ruff: noqa: PLR0912

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from data_agent_ctl.models import DataAgentSpec
    from data_agent_ctl.plan_schema import Plan


FORBIDDEN_ACTIONS: frozenset[str] = frozenset(
    {
        "create_service_account",
        "grant_public_iam",
        "grant_external_domain_iam",
    }
)


@dataclass(frozen=True)
class PolicyViolation:
    """A single policy violation discovered during plan review."""

    code: str
    message: str


@dataclass(frozen=True)
class PolicyResult:
    """Result of evaluating a plan against policy rules."""

    allowed: bool
    violations: tuple[PolicyViolation, ...] = ()


@dataclass(frozen=True)
class PolicyConfig:
    """Configurable policy settings loaded from policy file."""

    allow_public_members: bool = False
    allowed_external_domains: tuple[str, ...] = ()


def evaluate_plan(
    plan: Plan,
    allow_delete: bool = False,
    allow_stale_plan: bool = False,
) -> PolicyResult:
    """Evaluate static policy checks on a plan artifact."""
    violations: list[PolicyViolation] = []

    if plan.stale and not allow_stale_plan:
        violations.append(
            PolicyViolation(
                code="stale_plan",
                message="Plan is marked stale and cannot be applied.",
            )
        )

    for action in plan.actions:
        if action.kind in FORBIDDEN_ACTIONS:
            violations.append(
                PolicyViolation(
                    code="forbidden_action",
                    message=f"Action '{action.kind}' on '{action.resource}' is blocked by policy.",
                )
            )
        if action.destructive and not allow_delete:
            violations.append(
                PolicyViolation(
                    code="delete_not_allowed",
                    message=(
                        f"Destructive action '{action.kind}' on '{action.resource}' requires "
                        "--allow-delete."
                    ),
                )
            )
        if _has_public_member(action.payload):
            violations.append(
                PolicyViolation(
                    code="public_member_forbidden",
                    message=f"Action '{action.kind}' includes public IAM members.",
                )
            )

    return PolicyResult(allowed=not violations, violations=tuple(violations))


def load_policy_config(path: str | None) -> PolicyConfig:  # noqa: PLR0911
    """Load policy config from YAML or JSON file."""
    if path is None:
        return PolicyConfig()
    policy_path = Path(path)
    if not policy_path.exists():
        return PolicyConfig()
    text = policy_path.read_text(encoding="utf-8")
    raw = _parse_policy_text(text=text, path=policy_path)
    if not isinstance(raw, dict):
        return PolicyConfig()
    allow_public = bool(raw.get("allow_public_members", False))
    domains = raw.get("allowed_external_domains", [])
    if not isinstance(domains, list):
        domains = []
    return PolicyConfig(
        allow_public_members=allow_public,
        allowed_external_domains=tuple(str(domain) for domain in domains),
    )


def evaluate_specs(
    specs: list[DataAgentSpec],
    policy_config: PolicyConfig,
) -> PolicyResult:
    """Evaluate source specs against policy config constraints."""
    violations: list[PolicyViolation] = []
    for spec in specs:
        for binding in spec.iam_bindings:
            for member in binding.members:
                if (
                    member in {"allUsers", "allAuthenticatedUsers"}
                    and not policy_config.allow_public_members
                ):
                    violations.append(
                        PolicyViolation(
                            code="public_member_forbidden",
                            message=(
                                f"Spec '{spec.name}' contains public IAM member '{member}', "
                                "which policy forbids."
                            ),
                        )
                    )
                domain = _extract_domain(member)
                if domain is None:
                    continue
                if (
                    policy_config.allowed_external_domains
                    and domain not in policy_config.allowed_external_domains
                ):
                    violations.append(
                        PolicyViolation(
                            code="external_domain_forbidden",
                            message=(
                                f"Spec '{spec.name}' contains external domain member '{member}', "
                                "which policy forbids."
                            ),
                        )
                    )
    return PolicyResult(allowed=not violations, violations=tuple(violations))


def _extract_domain(member: str) -> str | None:
    if ":" not in member:
        return None
    _, value = member.split(":", maxsplit=1)
    if "@" not in value:
        return None
    return value.split("@", maxsplit=1)[1]


def _has_public_member(payload: dict[str, object]) -> bool:
    bindings = payload.get("bindings")
    if not isinstance(bindings, list):
        return False
    for item in bindings:
        if not isinstance(item, dict):
            continue
        members = item.get("members")
        if not isinstance(members, list):
            continue
        for member in members:
            if member in {"allUsers", "allAuthenticatedUsers"}:
                return True
    return False


def _parse_policy_text(text: str, path: Path) -> object:
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)
