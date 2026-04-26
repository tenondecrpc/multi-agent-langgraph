from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HTTP_METHODS = frozenset({"get", "put", "post", "delete", "patch", "head", "options", "trace"})
BYPASS_LABEL = "breaking-change-approved"


@dataclass(frozen=True)
class BreakingChange:
    code: str
    location: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "detail": self.detail}


def generate_openapi(output: Path, major: int) -> None:
    from backend.api_versioning import build_versioned_openapi
    from backend.app import create_app

    app = create_app()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_versioned_openapi(app, major), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def compare_openapi(base: dict[str, Any], head: dict[str, Any]) -> list[BreakingChange]:
    changes: list[BreakingChange] = []
    changes.extend(_compare_operations(base, head))
    changes.extend(_compare_component_schemas(base, head))
    return changes


def write_report(changes: list[BreakingChange], output: Path | None) -> None:
    report = {"breaking_changes": [change.as_dict() for change in changes]}
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(content, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def bypass_is_approved(event: dict[str, Any], registry_entries: list[dict[str, Any]]) -> bool:
    pull_request = event.get("pull_request") or {}
    labels = {label.get("name") for label in pull_request.get("labels", []) if isinstance(label, dict)}
    if BYPASS_LABEL not in labels:
        return False

    pr_number = pull_request.get("number") or event.get("number")
    head_sha = (pull_request.get("head") or {}).get("sha")
    for entry in registry_entries:
        if entry.get("label") != BYPASS_LABEL:
            continue
        if entry.get("pr_number") != pr_number:
            continue
        if entry.get("head_sha") != head_sha:
            continue
        if entry.get("issued_by_role") != "super_admin":
            continue
        if not str(entry.get("rationale") or "").strip():
            continue
        return True
    return False


def write_bypass_audit(
    *,
    event: dict[str, Any],
    approved: bool,
    output: Path,
    reason: str,
) -> None:
    pull_request = event.get("pull_request") or {}
    actor = event.get("sender", {}).get("login", "unknown")
    audit_event = {
        "event_type": "openapi_breaking_change_bypass",
        "approved": approved,
        "reason": reason,
        "label": BYPASS_LABEL,
        "actor": actor,
        "pr_number": pull_request.get("number") or event.get("number"),
        "head_sha": (pull_request.get("head") or {}).get("sha"),
        "created_at": datetime.now(tz=UTC).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit_event, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def _compare_operations(base: dict[str, Any], head: dict[str, Any]) -> list[BreakingChange]:
    changes: list[BreakingChange] = []
    base_paths = base.get("paths", {})
    head_paths = head.get("paths", {})
    for path, operations in base_paths.items():
        if path not in head_paths:
            changes.append(
                BreakingChange(
                    code="removed_path",
                    location=path,
                    detail="Path was removed from the public OpenAPI contract.",
                )
            )
            continue
        for method in operations:
            if method not in HTTP_METHODS:
                continue
            if method not in head_paths[path]:
                changes.append(
                    BreakingChange(
                        code="removed_operation",
                        location=f"{method.upper()} {path}",
                        detail="Operation was removed from the public OpenAPI contract.",
                    )
                )
    return changes


def _compare_component_schemas(base: dict[str, Any], head: dict[str, Any]) -> list[BreakingChange]:
    changes: list[BreakingChange] = []
    base_schemas = base.get("components", {}).get("schemas", {})
    head_schemas = head.get("components", {}).get("schemas", {})
    for name, base_schema in base_schemas.items():
        head_schema = head_schemas.get(name)
        if head_schema is None:
            changes.append(
                BreakingChange(
                    code="removed_schema",
                    location=f"components.schemas.{name}",
                    detail="Component schema was removed.",
                )
            )
            continue
        changes.extend(_compare_schema(name, base_schema, head_schema))
    return changes


def _compare_schema(name: str, base_schema: dict[str, Any], head_schema: dict[str, Any]) -> list[BreakingChange]:
    changes: list[BreakingChange] = []
    base_properties = base_schema.get("properties", {})
    head_properties = head_schema.get("properties", {})
    for property_name, base_property in base_properties.items():
        location = f"components.schemas.{name}.properties.{property_name}"
        head_property = head_properties.get(property_name)
        if head_property is None:
            changes.append(
                BreakingChange(
                    code="removed_property",
                    location=location,
                    detail="Schema property was removed.",
                )
            )
            continue
        if _schema_type(base_property) != _schema_type(head_property):
            changes.append(
                BreakingChange(
                    code="changed_property_type",
                    location=location,
                    detail=f"Type changed from {_schema_type(base_property)!r} to {_schema_type(head_property)!r}.",
                )
            )
        if _enum_was_narrowed(base_property, head_property):
            changes.append(
                BreakingChange(
                    code="narrowed_enum",
                    location=location,
                    detail="Allowed enum values were narrowed.",
                )
            )

    added_required = set(head_schema.get("required", [])).difference(base_schema.get("required", []))
    for property_name in sorted(added_required):
        changes.append(
            BreakingChange(
                code="added_required_property",
                location=f"components.schemas.{name}.required.{property_name}",
                detail="A newly required property may break existing clients.",
            )
        )
    return changes


def _schema_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"]
    if "anyOf" in schema:
        return "|".join(sorted(_schema_type(option) for option in schema["anyOf"]))
    if "oneOf" in schema:
        return "|".join(sorted(_schema_type(option) for option in schema["oneOf"]))
    return str(schema.get("type", "unknown"))


def _enum_was_narrowed(base_property: dict[str, Any], head_property: dict[str, Any]) -> bool:
    base_enum = base_property.get("enum")
    head_enum = head_property.get("enum")
    if not isinstance(base_enum, list) or not isinstance(head_enum, list):
        return False
    return set(head_enum) < set(base_enum)


def _cmd_generate(args: argparse.Namespace) -> int:
    generate_openapi(output=args.output, major=args.major)
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    changes = compare_openapi(load_json(args.base), load_json(args.head))
    write_report(changes, args.report)
    if not changes:
        return 0
    if args.mode == "warn":
        print(f"::warning::OpenAPI diff detected {len(changes)} breaking change(s); warn mode is active.")
        return 0
    if args.github_event and args.approval_registry and args.audit_output:
        approved = bypass_is_approved(load_json(args.github_event), load_jsonl(args.approval_registry))
        write_bypass_audit(
            event=load_json(args.github_event),
            approved=approved,
            output=args.audit_output,
            reason="approved_super_admin_label" if approved else "missing_super_admin_label_approval",
        )
        if approved:
            print("OpenAPI breaking changes accepted with audited super_admin bypass.")
            return 0
    print(f"OpenAPI diff detected {len(changes)} breaking change(s).")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and diff versioned OpenAPI contracts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--major", type=int, default=1)
    generate.set_defaults(func=_cmd_generate)

    diff = subparsers.add_parser("diff")
    diff.add_argument("--base", type=Path, required=True)
    diff.add_argument("--head", type=Path, required=True)
    diff.add_argument("--report", type=Path)
    diff.add_argument("--mode", choices=("warn", "block"), default="warn")
    diff.add_argument("--github-event", type=Path)
    diff.add_argument("--approval-registry", type=Path)
    diff.add_argument("--audit-output", type=Path)
    diff.set_defaults(func=_cmd_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
