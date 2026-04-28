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

"""CLI entry point for dagent."""
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false
# pylint: disable=W1405

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from dagent.drift.engine import detect_drift
from dagent.exit_codes import ExitCode
from dagent.inventory import collect_inventory, write_inventory
from dagent.metrics import METRICS
from dagent.models import IAMBinding
from dagent.plan.engine import build_plan
from dagent.plan_schema import Plan, load_plan, save_plan
from dagent.policy import PolicyResult, evaluate_plan, evaluate_specs, load_policy_config
from dagent.providers.google_gemini_data_analytics import GoogleGeminiDataAnalyticsProvider
from dagent.sources.dbt import DbtSourceAdapter
from dagent.sources.yaml import YamlSourceAdapter


def _build_parser() -> ArgumentParser:  # noqa: PLR0915
    parser = ArgumentParser(
        prog="dagent",
        description=(
            "Manage analytics data-agent lifecycle with non-interactive "
            "validate/plan/apply workflows."
        ),
        epilog=(
            "Examples:\n"
            "  dagent validate --source dbt --manifest target/manifest.json\n"
            "  dagent plan --source dbt --manifest target/manifest.json "
            "--projects analytics-dev --out target/dagent.plan.json\n"
            "  dagent apply target/dagent.plan.json --yes\n"
        ),
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-format",
        choices=("text", "json"),
        default="text",
        help="Global log format for command output.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate source artifacts and command inputs.",
        epilog=(
            "Examples:\n"
            "  dagent validate --source dbt --manifest target/manifest.json\n"
            "  dagent validate --source dbt --manifest target/manifest.json "
            "--run-results target/run_results.json\n"
        ),
        formatter_class=RawDescriptionHelpFormatter,
    )
    validate_parser.add_argument(
        "--source",
        required=True,
        choices=("dbt", "yaml"),
        help="Desired-state source adapter.",
    )
    validate_parser.add_argument(
        "--manifest",
        required=True,
        help="Path to source manifest file (for dbt: target/manifest.json).",
    )
    validate_parser.add_argument(
        "--run-results",
        required=False,
        help="Optional path to source run results metadata.",
    )
    validate_parser.add_argument(
        "--policy",
        required=False,
        help="Optional policy YAML/JSON file.",
    )
    validate_parser.add_argument(
        "--specs",
        nargs="+",
        required=False,
        help="One or more YAML spec paths when --source yaml is used.",
    )
    validate_parser.add_argument(
        "--project",
        required=False,
        default="analytics-dev",
        help="Default project for YAML source specs.",
    )
    validate_parser.add_argument("--location", required=False, default="global")
    validate_parser.set_defaults(func=_run_validate)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Generate a plan artifact from source state.",
        epilog=(
            "Examples:\n"
            "  dagent plan --source dbt --manifest target/manifest.json "
            "--projects analytics-dev --out target/dagent.plan.json\n"
        ),
        formatter_class=RawDescriptionHelpFormatter,
    )
    plan_parser.add_argument("--source", required=True, choices=("dbt", "yaml"))
    plan_parser.add_argument("--manifest", required=True)
    plan_parser.add_argument(
        "--projects",
        required=True,
        nargs="+",
        help="One or more target projects.",
    )
    plan_parser.add_argument("--run-results", required=False)
    plan_parser.add_argument("--policy", required=False)
    plan_parser.add_argument("--location", required=False, default="global")
    plan_parser.add_argument("--specs", nargs="+", required=False)
    plan_parser.add_argument(
        "--out",
        required=True,
        help="Path for generated plan artifact.",
    )
    plan_parser.set_defaults(func=_run_plan)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply a previously generated plan artifact.",
        epilog=(
            "Examples:\n"
            "  dagent apply target/dagent.plan.json --yes\n"
            "\n"
            "Error examples:\n"
            "  Missing confirmation bypass: dagent apply PLAN --yes\n"
        ),
        formatter_class=RawDescriptionHelpFormatter,
    )
    apply_parser.add_argument("plan_file", help="Path to plan artifact JSON file.")
    apply_parser.add_argument(
        "--yes",
        action="store_true",
        help="Explicitly confirm non-interactive apply.",
    )
    apply_parser.add_argument(
        "--allow-stale-plan",
        action="store_true",
        help="Allow applying stale plan artifacts.",
    )
    apply_parser.add_argument(
        "--allow-delete",
        action="store_true",
        help="Allow destructive actions in plan apply.",
    )
    apply_parser.set_defaults(func=_run_apply)

    drift_parser = subparsers.add_parser(
        "drift",
        help="Detect and report desired-vs-remote drift.",
        formatter_class=RawDescriptionHelpFormatter,
    )
    drift_subcommands = drift_parser.add_subparsers(dest="drift_command", required=True)

    detect_parser = drift_subcommands.add_parser("detect", help="Detect drift.")
    _add_source_args(parser=detect_parser)
    _add_project_args(parser=detect_parser)
    _add_drift_output_args(parser=detect_parser)
    detect_parser.set_defaults(func=_run_drift_detect)

    explain_parser = drift_subcommands.add_parser("explain", help="Explain drift findings.")
    _add_source_args(parser=explain_parser)
    _add_project_args(parser=explain_parser)
    explain_parser.set_defaults(func=_run_drift_explain)

    remediate_parser = drift_subcommands.add_parser("remediate", help="Generate remediation plan.")
    _add_source_args(parser=remediate_parser)
    _add_project_args(parser=remediate_parser)
    remediate_parser.add_argument("--out", required=True)
    remediate_parser.set_defaults(func=_run_drift_remediate)

    report_parser = drift_subcommands.add_parser("report", help="Generate drift report artifact.")
    _add_source_args(parser=report_parser)
    _add_project_args(parser=report_parser)
    report_parser.add_argument("--format", choices=("html", "markdown", "json"), required=True)
    report_parser.add_argument("--out", required=True)
    report_parser.set_defaults(func=_run_drift_report)

    iam_parser = subparsers.add_parser("iam", help="Manage IAM bindings.")
    iam_subcommands = iam_parser.add_subparsers(dest="iam_command", required=True)

    iam_get_parser = iam_subcommands.add_parser("get", help="Get IAM policy bindings.")
    iam_get_parser.add_argument("--resource", required=True)
    iam_get_parser.add_argument("--format", choices=("json", "table"), default="json")
    iam_get_parser.set_defaults(func=_run_iam_get)

    iam_set_parser = iam_subcommands.add_parser("set", help="Set IAM policy bindings.")
    iam_set_parser.add_argument("--resource", required=True)
    iam_set_parser.add_argument("--bindings-file", required=True)
    iam_set_parser.add_argument("--yes", action="store_true")
    iam_set_parser.set_defaults(func=_run_iam_set)

    inventory_parser = subparsers.add_parser("inventory", help="Inventory commands.")
    inventory_subcommands = inventory_parser.add_subparsers(
        dest="inventory_command",
        required=True,
    )
    inventory_export = inventory_subcommands.add_parser("export", help="Export inventory.")
    inventory_export.add_argument("--projects", nargs="+", required=True)
    inventory_export.add_argument("--location", default="global")
    inventory_export.add_argument("--format", choices=("csv", "json"), required=True)
    inventory_export.add_argument("--out", required=True)
    inventory_export.set_defaults(func=_run_inventory_export)
    return parser


def _run_validate(args: Namespace) -> int:  # noqa: PLR0911
    adapter_or_error = _build_source_adapter(args=args)
    if not isinstance(adapter_or_error, tuple):
        print(adapter_or_error, file=sys.stderr)
        return ExitCode.VALIDATION_FAILED
    adapter, source_paths = adapter_or_error
    diagnostics = adapter.validate()
    if diagnostics:
        _print_diagnostics(diagnostics=diagnostics)
        return ExitCode.VALIDATION_FAILED
    specs = adapter.load_specs()
    policy_result = evaluate_specs(specs=specs, policy_config=load_policy_config(args.policy))
    if not policy_result.allowed:
        _print_policy_violations(policy_result)
        return ExitCode.VALIDATION_FAILED
    _emit_log(
        args=args,
        event="validation.completed",
        details={
            "source": adapter.source_name,
            "spec_count": len(specs),
            "source_paths": ",".join(str(path) for path in source_paths),
        },
    )
    METRICS.increment("dagent_agents_desired", len(specs))
    return ExitCode.SUCCESS


def _run_plan(args: Namespace) -> int:
    adapter_or_error = _build_source_adapter(args=args)
    if not isinstance(adapter_or_error, tuple):
        print(adapter_or_error, file=sys.stderr)
        return ExitCode.VALIDATION_FAILED
    adapter, source_paths = adapter_or_error
    diagnostics = adapter.validate()
    if diagnostics:
        _print_diagnostics(diagnostics=diagnostics)
        return ExitCode.VALIDATION_FAILED
    specs = adapter.load_specs()
    provider = GoogleGeminiDataAnalyticsProvider()
    remote_agents = _list_remote_agents(
        provider=provider,
        projects=args.projects,
        location=args.location,
    )
    plan = build_plan(
        desired_specs=specs,
        remote_agents=remote_agents,
        source_name=adapter.source_name,
        projects=args.projects,
        location=args.location,
        source_hash=_compute_source_hash(source_paths=source_paths),
        policy_path=args.policy,
    )
    output_path = Path(args.out)
    save_plan(path=output_path, plan=plan)
    _emit_log(
        args=args,
        event="plan.generated",
        details={
            "plan_written": str(output_path),
            "actions": len(plan.actions),
            "next": "dagent apply <plan-file> --yes",
        },
    )
    METRICS.increment("dagent_apply_actions", len(plan.actions))
    return ExitCode.SUCCESS


def _run_apply(args: Namespace) -> int:
    code: ExitCode
    plan = _load_apply_plan(args)
    if not isinstance(plan, Plan):
        code = plan
    else:
        policy = evaluate_plan(
            plan=plan,
            allow_delete=args.allow_delete,
            allow_stale_plan=args.allow_stale_plan,
        )
        if not policy.allowed:
            _print_policy_violations(policy)
            code = _policy_to_exit_code(policy)
        else:
            METRICS.increment("dagent_apply_actions", len(plan.actions))
            _emit_log(
                args=args,
                event="apply.simulated",
                details={
                    "apply_simulated": "true",
                    "actions": len(plan.actions),
                    "resource_count": len({action.resource for action in plan.actions}),
                },
            )
            code = ExitCode.SUCCESS
    return code


def _load_apply_plan(args: Namespace) -> Plan | ExitCode:
    """Validate apply prerequisites and load plan from disk."""
    result: Plan | ExitCode
    if not args.yes:
        print(
            "Error: apply requires explicit confirmation flag.\n"
            f"  dagent apply {args.plan_file} --yes",
            file=sys.stderr,
        )
        result = ExitCode.FORBIDDEN_ACTION
    else:
        plan_path = Path(args.plan_file)
        if not plan_path.exists():
            print(
                f"Error: plan file does not exist.\n  dagent apply {plan_path} --yes",
                file=sys.stderr,
            )
            result = ExitCode.VALIDATION_FAILED
        else:
            try:
                result = load_plan(plan_path)
            except (TypeError, ValueError) as exc:
                print(f"Error: {exc}", file=sys.stderr)
                result = ExitCode.VALIDATION_FAILED
    return result


def _print_policy_violations(policy: PolicyResult) -> None:
    """Print policy violations with machine-readable prefixes."""
    for violation in policy.violations:
        print(f"policy_violation={violation.code} {violation.message}", file=sys.stderr)


def _run_drift_detect(args: Namespace) -> int:
    findings, summary = _collect_drift(args=args)
    METRICS.increment("dagent_drift_findings", summary.total)
    _print_findings(findings=findings)
    threshold = args.fail_on
    if threshold and _is_threshold_exceeded(summary=summary, threshold=threshold):
        return ExitCode.DRIFT_DETECTED
    return ExitCode.SUCCESS


def _run_drift_explain(args: Namespace) -> int:
    findings, _ = _collect_drift(args=args)
    for finding in findings:
        print(
            f"type={finding.finding_type} severity={finding.severity.value} "
            f"resource={finding.resource} remediation={finding.remediation_action}"
        )
    return ExitCode.SUCCESS


def _run_drift_remediate(args: Namespace) -> int:
    adapter_or_error = _build_source_adapter(args=args)
    if not isinstance(adapter_or_error, tuple):
        print(adapter_or_error, file=sys.stderr)
        return ExitCode.VALIDATION_FAILED
    adapter, source_paths = adapter_or_error
    specs = adapter.load_specs()
    provider = GoogleGeminiDataAnalyticsProvider()
    remote_agents = _list_remote_agents(
        provider=provider, projects=args.projects, location=args.location
    )
    plan = build_plan(
        desired_specs=specs,
        remote_agents=remote_agents,
        source_name=adapter.source_name,
        projects=args.projects,
        location=args.location,
        source_hash=_compute_source_hash(source_paths=source_paths),
        policy_path=args.policy,
    )
    save_plan(path=Path(args.out), plan=plan)
    print(f"plan_written={args.out} actions={len(plan.actions)}")
    return ExitCode.SUCCESS


def _run_drift_report(args: Namespace) -> int:
    findings, summary = _collect_drift(args=args)
    METRICS.increment("dagent_drift_findings", summary.total)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        payload = {
            "summary": summary.__dict__,
            "findings": [finding.__dict__ for finding in findings],
        }
        output_path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    elif args.format == "html":
        output_path.write_text(
            _render_html_report(findings=findings, summary=summary), encoding="utf-8"
        )
    else:
        output_path.write_text(
            _render_markdown_report(findings=findings, summary=summary), encoding="utf-8"
        )
    print(f"report_written={output_path}")
    return ExitCode.SUCCESS


def _run_iam_get(args: Namespace) -> int:
    provider = GoogleGeminiDataAnalyticsProvider()
    bindings = provider.get_iam_policy(resource=args.resource)
    if args.format == "json":
        data = [{"role": binding.role, "members": list(binding.members)} for binding in bindings]
        print(json.dumps({"resource": args.resource, "bindings": data}, indent=2))
        return ExitCode.SUCCESS
    for binding in bindings:
        print(f"role={binding.role} members={','.join(binding.members)}")
    return ExitCode.SUCCESS


def _run_iam_set(args: Namespace) -> int:  # noqa: PLR0911
    if not args.yes:
        print(
            "Error: iam set requires explicit confirmation flag.\n"
            "  dagent iam set --resource <resource> --bindings-file <path> --yes",
            file=sys.stderr,
        )
        return ExitCode.FORBIDDEN_ACTION
    bindings_path = Path(args.bindings_file)
    if not bindings_path.exists():
        print(f"Error: bindings file does not exist: {bindings_path}", file=sys.stderr)
        return ExitCode.VALIDATION_FAILED
    payload = json.loads(bindings_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("Error: bindings file root must be an object.", file=sys.stderr)
        return ExitCode.VALIDATION_FAILED
    provider = GoogleGeminiDataAnalyticsProvider()
    bindings = _parse_bindings_payload(payload)
    result = provider.set_iam_policy(resource=args.resource, bindings=bindings)
    if result.success:
        print(f"iam_updated=true resource={result.resource}")
        return ExitCode.SUCCESS
    return ExitCode.API_ERROR


def _run_inventory_export(args: Namespace) -> int:
    provider = GoogleGeminiDataAnalyticsProvider()
    rows = collect_inventory(provider=provider, projects=args.projects, location=args.location)
    METRICS.increment("dagent_agents_remote", len(rows))
    write_inventory(rows=rows, output_path=Path(args.out), output_format=args.format)
    print(f"inventory_exported={args.out} rows={len(rows)}")
    return ExitCode.SUCCESS


def _add_source_args(parser: ArgumentParser) -> None:
    parser.add_argument("--source", choices=("dbt", "yaml"), required=True)
    parser.add_argument("--manifest", required=False)
    parser.add_argument("--specs", nargs="+", required=False)
    parser.add_argument("--project", required=False, default="analytics-dev")
    parser.add_argument("--policy", required=False)


def _add_project_args(parser: ArgumentParser) -> None:
    parser.add_argument("--projects", nargs="+", required=True)
    parser.add_argument("--location", default="global")


def _add_drift_output_args(parser: ArgumentParser) -> None:
    parser.add_argument("--fail-on", choices=("low", "medium", "high", "critical"), required=False)
    parser.add_argument("--format", choices=("table", "json"), default="table")


def _build_source_adapter(args: Namespace) -> tuple[object, list[Path]] | str:  # noqa: PLR0911
    if args.source == "dbt":
        if not args.manifest:
            return "Error: --manifest is required when --source dbt."
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            return f"Error: manifest file does not exist: {manifest_path}"
        adapter = DbtSourceAdapter(
            manifest_path=manifest_path,
            default_project_id=args.project if hasattr(args, "project") else args.projects[0],
            default_location=args.location if hasattr(args, "location") else "global",
        )
        return adapter, [manifest_path]
    if not args.specs:
        return "Error: --specs is required when --source yaml."
    spec_paths = [Path(path) for path in args.specs]
    adapter = YamlSourceAdapter(
        spec_paths=spec_paths,
        default_project_id=args.project if hasattr(args, "project") else args.projects[0],
        default_location=args.location if hasattr(args, "location") else "global",
    )
    return adapter, spec_paths


def _list_remote_agents(
    provider: GoogleGeminiDataAnalyticsProvider,
    projects: list[str],
    location: str,
) -> list[object]:
    remote_agents = []
    for project_id in projects:
        remote_agents.extend(provider.list_agents(project_id=project_id, location=location))
    return remote_agents


def _print_diagnostics(diagnostics: list[object]) -> None:
    for diagnostic in diagnostics:
        path = diagnostic.path or "-"
        print(
            f"diagnostic={diagnostic.code} level={diagnostic.level.value} "
            f"path={path} message={diagnostic.message}",
            file=sys.stderr,
        )


def _policy_to_exit_code(policy: PolicyResult) -> ExitCode:
    for violation in policy.violations:
        if violation.code == "stale_plan":
            return ExitCode.STALE_PLAN
    return ExitCode.FORBIDDEN_ACTION


def _collect_drift(args: Namespace) -> tuple[list[object], object]:
    adapter_or_error = _build_source_adapter(args=args)
    if not isinstance(adapter_or_error, tuple):
        print(adapter_or_error, file=sys.stderr)
        raise SystemExit(int(ExitCode.VALIDATION_FAILED))
    adapter, _ = adapter_or_error
    diagnostics = adapter.validate()
    if diagnostics:
        _print_diagnostics(diagnostics=diagnostics)
        raise SystemExit(int(ExitCode.VALIDATION_FAILED))
    specs = adapter.load_specs()
    provider = GoogleGeminiDataAnalyticsProvider()
    remote_agents = _list_remote_agents(
        provider=provider, projects=args.projects, location=args.location
    )
    return detect_drift(desired_specs=specs, remote_agents=remote_agents)


def _print_findings(findings: list[object]) -> None:
    for finding in findings:
        print(
            f"type={finding.finding_type} severity={finding.severity.value} "
            f"resource={finding.resource} message={finding.message}"
        )


def _is_threshold_exceeded(summary: object, threshold: str) -> bool:
    weights = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    summary_counts = {
        "low": summary.low,
        "medium": summary.medium,
        "high": summary.high,
        "critical": summary.critical,
    }
    threshold_rank = weights[threshold]
    for severity, count in summary_counts.items():
        if count > 0 and weights[severity] >= threshold_rank:
            return True
    return False


def _render_markdown_report(findings: list[object], summary: object) -> str:
    lines = [
        "# Dagent Drift Report",
        "",
        f"- Total: {summary.total}",
        f"- Low: {summary.low}",
        f"- Medium: {summary.medium}",
        f"- High: {summary.high}",
        f"- Critical: {summary.critical}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(
        [
            f"- **{finding.severity.value}** `{finding.finding_type}` "
            f"on `{finding.resource}`: {finding.message}"
            for finding in findings
        ]
    )
    return "\n".join(lines) + "\n"


def _render_html_report(findings: list[object], summary: object) -> str:
    list_items = "".join(
        (
            f"<li><strong>{finding.severity.value}</strong> "
            f"<code>{finding.finding_type}</code> on <code>{finding.resource}</code>: "
            f"{finding.message}</li>"
        )
        for finding in findings
    )
    return (
        "<html><body>"
        f"<h1>Dagent Drift Report</h1><p>Total: {summary.total}</p>"
        "<ul>"
        f"{list_items}"
        "</ul></body></html>\n"
    )


def _compute_source_hash(source_paths: list[Path]) -> str:
    digest = sha256()
    for path in sorted(source_paths):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _emit_log(args: Namespace, event: str, details: dict[str, object]) -> None:
    if args.log_format == "json":
        payload = {
            "event": event,
            **details,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),  # noqa: UP017
        }
        print(json.dumps(payload))
        return
    text = " ".join(f"{key}={value}" for key, value in details.items())
    print(f"{event} {text}")


def _parse_bindings_payload(payload: dict[str, object]) -> tuple[IAMBinding, ...]:
    bindings_raw = payload.get("bindings", [])
    if not isinstance(bindings_raw, list):
        return ()
    bindings: list[IAMBinding] = []
    for item in bindings_raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        members = item.get("members", [])
        if not role or not isinstance(members, list):
            continue
        values = tuple(str(member) for member in members if isinstance(member, str))
        bindings.append(IAMBinding(role=role, members=values))
    return tuple(bindings)


def main(argv: list[str] | None = None) -> int:
    """Run dagent CLI and return process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
