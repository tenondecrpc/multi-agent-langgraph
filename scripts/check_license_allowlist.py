#!/usr/bin/env python3
"""Validate dependency licenses against the project allowlist.

Reads a license report JSON (from pip-licenses or license-checker) and
compares each dependency license against the allowed and denied lists.
Exits non-zero if any dependency uses a denied license or an unlisted license.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_allowlist(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_license_report(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    raise ValueError(f"Unexpected license report format: {type(data)}")


def normalize_license(name: str) -> str:
    return " ".join(name.strip().split())


def check_licenses(
    report_path: str,
    allowlist_path: str,
) -> list[str]:
    allowlist = load_allowlist(allowlist_path)
    allowed = {normalize_license(lic) for lic in allowlist["allowed_licenses"]}
    denied = {normalize_license(lic) for lic in allowlist["denied_licenses"]}
    report = load_license_report(report_path)

    violations: list[str] = []
    for entry in report:
        name = entry.get("name", entry.get("package", "unknown"))
        version = entry.get("version", "unknown")
        license_raw = entry.get("license", entry.get("licenses", "UNKNOWN"))
        if isinstance(license_raw, list):
            license_raw = ", ".join(license_raw)
        license_name = normalize_license(license_raw)

        if license_name in denied:
            violations.append(
                f"VIOLATION: {name} {version} uses denied license: {license_name}"
            )
        elif license_name not in allowed:
            violations.append(
                f"WARNING: {name} {version} uses unlisted license: {license_name} "
                f"(not in allowlist; requires review)"
            )

    return violations


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <license-report.json> <allowlist.json>")
        sys.exit(1)

    report_path = sys.argv[1]
    allowlist_path = sys.argv[2]

    if not Path(report_path).exists():
        print(f"License report not found: {report_path}")
        print("Run pip-licenses or license-checker first.")
        sys.exit(0)

    violations = check_licenses(report_path, allowlist_path)

    if violations:
        for v in violations:
            print(v)
        denied_count = sum(1 for v in violations if v.startswith("VIOLATION"))
        if denied_count > 0:
            print(f"\n{denied_count} denied license(s) found. Build blocked.")
            sys.exit(1)
        else:
            print(f"\n{len(violations)} unlisted license(s) require review.")
            sys.exit(0)
    else:
        print("All licenses comply with the allowlist.")
        sys.exit(0)


if __name__ == "__main__":
    main()
