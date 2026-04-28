# ADR 0003: Enforce plan-gated apply and safety policy

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Maintainers

## Context

`dagent apply` can change remote state. Without strict safety gates, automation can apply stale or unsafe actions, or mutate resources without an auditable plan.

## Decision

All mutating operations are plan-gated and policy-gated:

- `apply` consumes an explicit plan file artifact, not ad-hoc desired state input.
- Mutations require an explicit confirmation bypass (`--yes`) for non-interactive automation.
- Policy checks run before mutation and reject forbidden actions.
- Stale-plan detection is treated as a hard failure.
- CI usage expects non-interactive invocation with explicit plan artifact handling.

Stable invariants:

- No remote mutation without a plan file.
- Policy violations block apply before side effects.
- Confirmation is explicit for automated mutation flows.

## Consequences

- Safer and auditable deployments with reproducible plan/apply separation.
- Additional operational step to generate and store plans before apply.
- Implementation must maintain policy evaluation and plan metadata validation.

## Alternatives considered

- **Direct apply from source artifacts:** Rejected; weaker auditability and higher risk of unintended changes.
- **Interactive confirmation only:** Rejected; incompatible with CI and agent-driven automation.
- **Best-effort warnings instead of hard gates:** Rejected; fails closed-loop safety expectations.

## Trade-offs

- We accept extra pipeline complexity in exchange for stronger safety guarantees.
- We optimize for controlled mutation over shortest-path operator convenience.

## References

- [AGENTS.md](../../AGENTS.md)
- [ADR 0002](./0002-define-non-interactive-cli-contract-for-dagent.md)
- [Product design draft](../product_design.md)
