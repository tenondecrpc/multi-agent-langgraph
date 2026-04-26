from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from lint_alert_runbooks import lint_alert_runbooks, main


def test_existing_paging_alerts_reference_existing_runbooks() -> None:
    report = lint_alert_runbooks(Path("docs/alerts"), Path("docs/runbooks"))

    assert report.passed is True


def test_lint_blocks_paging_alert_without_runbook_url(tmp_path: Path) -> None:
    alerts_dir = tmp_path / "alerts"
    runbooks_dir = tmp_path / "runbooks"
    alerts_dir.mkdir()
    runbooks_dir.mkdir()
    (alerts_dir / "rules.yaml").write_text(
        """
groups:
  - name: sample
    rules:
      - alert: MissingRunbook
        labels:
          severity: page
""",
        encoding="utf-8",
    )

    exit_code = main(["--alerts-dir", str(alerts_dir), "--runbooks-dir", str(runbooks_dir)])

    assert exit_code == 1


def test_lint_warns_on_orphaned_runbook_without_failing(tmp_path: Path) -> None:
    alerts_dir = tmp_path / "alerts"
    runbooks_dir = tmp_path / "runbooks"
    alerts_dir.mkdir()
    runbooks_dir.mkdir()
    (runbooks_dir / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    (alerts_dir / "rules.yaml").write_text(
        """
groups:
  - name: sample
    rules:
      - alert: Ticket
        labels:
          severity: warning
""",
        encoding="utf-8",
    )

    report = lint_alert_runbooks(alerts_dir, runbooks_dir)

    assert report.passed is True
    assert report.warnings == [f"orphaned runbook: {runbooks_dir / 'orphan.md'}"]
