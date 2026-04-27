from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AlertRunbookIssue:
    alert_name: str
    message: str


@dataclass(frozen=True)
class AlertRunbookReport:
    issues: list[AlertRunbookIssue]
    warnings: list[str]

    @property
    def passed(self) -> bool:
        return not self.issues


def lint_alert_runbooks(alerts_dir: Path, runbooks_dir: Path) -> AlertRunbookReport:
    alert_blocks = _read_alert_blocks(alerts_dir)
    referenced_runbooks: set[Path] = set()
    issues: list[AlertRunbookIssue] = []

    for alert_name, block in alert_blocks:
        if not _has_field(block, "severity", "page"):
            continue
        runbook_url = _field_value(block, "runbook_url")
        if runbook_url is None:
            issues.append(AlertRunbookIssue(alert_name, "missing runbook_url label"))
            continue
        runbook_path = Path(runbook_url)
        if not runbook_path.exists():
            issues.append(AlertRunbookIssue(alert_name, f"runbook does not exist: {runbook_url}"))
            continue
        try:
            runbook_path.relative_to(runbooks_dir)
        except ValueError:
            issues.append(AlertRunbookIssue(alert_name, f"runbook is outside {runbooks_dir}: {runbook_url}"))
            continue
        referenced_runbooks.add(runbook_path)

    warnings = [
        f"orphaned runbook: {path}"
        for path in sorted(runbooks_dir.glob("*.md"))
        if path not in referenced_runbooks
    ]
    return AlertRunbookReport(issues=issues, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alerts-dir", default="operations/alerts")
    parser.add_argument("--runbooks-dir", default="docs/runbooks")
    args = parser.parse_args(argv)

    report = lint_alert_runbooks(Path(args.alerts_dir), Path(args.runbooks_dir))
    for warning in report.warnings:
        print(f"warning: {warning}")
    for issue in report.issues:
        print(f"error: {issue.alert_name}: {issue.message}")
    return 0 if report.passed else 1


def _read_alert_blocks(alerts_dir: Path) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_block: list[str] = []
    for path in sorted(alerts_dir.glob("*.yaml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("- alert:"):
                if current_name is not None:
                    blocks.append((current_name, current_block))
                current_name = stripped.split(":", 1)[1].strip()
                current_block = [stripped]
                continue
            if current_name is not None:
                current_block.append(stripped)
    if current_name is not None:
        blocks.append((current_name, current_block))
    return blocks


def _field_value(block: list[str], key: str) -> str | None:
    prefix = f"{key}:"
    for line in block:
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def _has_field(block: list[str], key: str, value: str) -> bool:
    return _field_value(block, key) == value


if __name__ == "__main__":
    raise SystemExit(main())
