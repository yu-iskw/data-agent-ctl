# ADR 0002: Define non-interactive CLI contract for dagent

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Maintainers

## Context

`dagent` is intended to be run by both humans and coding agents in CI/CD and local automation.
Interactive prompts or ambiguous CLI behavior would make the tool unreliable for automated workflows and increase failure rates in pipelines.

## Decision

`dagent` commands MUST be agent-friendly and non-interactive by default:

- All required inputs are explicit flags or arguments.
- Subcommands expose localized help (`--help`) with concrete examples.
- Missing required input fails fast with a clear remediation command.
- Command behavior and output are predictable across local and CI runs.
- Exit codes are stable and documented for machine handling.
- Success output includes concise machine-usable signals.

Stable invariants:

- No command requires interactive menus/prompts to complete.
- Mutating behavior is always explicit through command inputs.
- Error messages include actionable next steps.

## Consequences

- Automation reliability improves for CI jobs, scripts, and coding agents.
- CLI implementation requires stronger argument validation and help design discipline.
- Some human convenience features (implicit prompts) are intentionally limited to preserve deterministic behavior.

## Alternatives considered

- **Human-first interactive CLI with optional flags:** Rejected; too easy for automation to hang or branch unpredictably.
- **JSON-only API without a CLI contract:** Rejected; does not satisfy direct operator and CI usability requirements.

## Trade-offs

- We accept more up-front CLI design effort to reduce long-term operational toil.
- We prioritize deterministic execution over interactive ergonomics.

## References

- [AGENTS.md](../../AGENTS.md)
- [Product design draft](../product_design.md)
