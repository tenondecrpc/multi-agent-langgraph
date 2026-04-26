from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from openapi_diff_gate import BYPASS_LABEL, bypass_is_approved, compare_openapi, main


def test_openapi_diff_detects_removed_operation() -> None:
    base = {"paths": {"/api/v1/runs/{run_id}": {"get": {"responses": {"200": {"description": "ok"}}}}}}
    head = {"paths": {"/api/v1/runs/{run_id}": {}}}

    changes = compare_openapi(base, head)

    assert [change.code for change in changes] == ["removed_operation"]
    assert changes[0].location == "GET /api/v1/runs/{run_id}"


def test_openapi_diff_detects_component_schema_breaks() -> None:
    base = {
        "paths": {},
        "components": {
            "schemas": {
                "Run": {
                    "required": ["run_id"],
                    "properties": {
                        "run_id": {"type": "string"},
                        "status": {"type": "string", "enum": ["planned", "completed"]},
                    },
                }
            }
        },
    }
    head = {
        "paths": {},
        "components": {
            "schemas": {
                "Run": {
                    "required": ["run_id", "status"],
                    "properties": {
                        "run_id": {"type": "integer"},
                        "status": {"type": "string", "enum": ["completed"]},
                    },
                }
            }
        },
    }

    changes = compare_openapi(base, head)

    assert {change.code for change in changes} == {
        "added_required_property",
        "changed_property_type",
        "narrowed_enum",
    }


def test_breaking_change_bypass_requires_super_admin_registry_entry() -> None:
    event = {
        "number": 42,
        "pull_request": {
            "number": 42,
            "head": {"sha": "abc123"},
            "labels": [{"name": BYPASS_LABEL}],
        },
    }

    assert not bypass_is_approved(event, [])
    assert not bypass_is_approved(
        event,
        [
            {
                "pr_number": 42,
                "head_sha": "abc123",
                "label": BYPASS_LABEL,
                "issued_by_role": "admin",
                "rationale": "emergency partner migration",
            }
        ],
    )
    assert bypass_is_approved(
        event,
        [
            {
                "pr_number": 42,
                "head_sha": "abc123",
                "label": BYPASS_LABEL,
                "issued_by_role": "super_admin",
                "rationale": "emergency partner migration",
            }
        ],
    )


def test_diff_command_blocks_breaking_change_without_approved_bypass(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    report = tmp_path / "report.json"
    base.write_text(json.dumps({"paths": {"/api/v1/runs/{run_id}": {"get": {}}}}), encoding="utf-8")
    head.write_text(json.dumps({"paths": {}}), encoding="utf-8")

    exit_code = main(
        [
            "diff",
            "--base",
            str(base),
            "--head",
            str(head),
            "--report",
            str(report),
            "--mode",
            "block",
        ]
    )

    assert exit_code == 1
    assert json.loads(report.read_text(encoding="utf-8"))["breaking_changes"][0]["code"] == "removed_path"


def test_diff_command_passes_non_breaking_change(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    report = tmp_path / "report.json"
    contract = {
        "paths": {
            "/api/v1/runs/{run_id}": {"get": {}},
        },
        "components": {
            "schemas": {
                "Run": {
                    "required": ["run_id"],
                    "properties": {"run_id": {"type": "string"}},
                }
            }
        },
    }
    base.write_text(json.dumps(contract), encoding="utf-8")
    head.write_text(json.dumps(contract), encoding="utf-8")

    exit_code = main(
        [
            "diff",
            "--base",
            str(base),
            "--head",
            str(head),
            "--report",
            str(report),
            "--mode",
            "block",
        ]
    )

    assert exit_code == 0
    assert json.loads(report.read_text(encoding="utf-8"))["breaking_changes"] == []
