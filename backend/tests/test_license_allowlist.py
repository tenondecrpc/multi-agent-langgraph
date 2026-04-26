"""Tests for the license allowlist checker script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def allowlist(tmp_path: Path) -> Path:
    data = {
        "allowed_licenses": ["MIT License", "Apache Software License", "BSD-3-Clause"],
        "denied_licenses": ["GNU General Public License v3 (GPLv3)", "AGPL-3.0"],
    }
    path = tmp_path / "allowlist.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture()
def compliant_report(tmp_path: Path) -> Path:
    data = [
        {"name": "requests", "version": "2.31.0", "license": "Apache Software License"},
        {"name": "flask", "version": "3.0.0", "license": "BSD-3-Clause"},
    ]
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture()
def denied_report(tmp_path: Path) -> Path:
    data = [
        {"name": "requests", "version": "2.31.0", "license": "Apache Software License"},
        {"name": "gpl-lib", "version": "1.0.0", "license": "GNU General Public License v3 (GPLv3)"},
    ]
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture()
def unlisted_report(tmp_path: Path) -> Path:
    data = [
        {"name": "requests", "version": "2.31.0", "license": "Apache Software License"},
        {"name": "unknown-lib", "version": "0.1.0", "license": "Custom License v1"},
    ]
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    return path


def run_checker(report: Path, allowlist: Path) -> subprocess.CompletedProcess:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "check_license_allowlist.py"
    return subprocess.run(
        [sys.executable, str(script), str(report), str(allowlist)],
        capture_output=True,
        text=True,
    )


def test_compliant_report_passes(allowlist: Path, compliant_report: Path) -> None:
    result = run_checker(compliant_report, allowlist)
    assert result.returncode == 0
    assert "comply" in result.stdout


def test_denied_license_is_flagged(allowlist: Path, denied_report: Path) -> None:
    result = run_checker(denied_report, allowlist)
    assert result.returncode == 1
    assert "VIOLATION" in result.stdout
    assert "GPLv3" in result.stdout


def test_unlisted_license_is_warned(allowlist: Path, unlisted_report: Path) -> None:
    result = run_checker(unlisted_report, allowlist)
    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "unlisted" in result.stdout


def test_multiple_violations_are_reported(allowlist: Path, tmp_path: Path) -> None:
    data = [
        {"name": "gpl-lib", "version": "1.0.0", "license": "GNU General Public License v3 (GPLv3)"},
        {"name": "agpl-lib", "version": "2.0.0", "license": "AGPL-3.0"},
        {"name": "unknown", "version": "0.1.0", "license": "Weird License"},
    ]
    report = tmp_path / "report.json"
    report.write_text(json.dumps(data))
    result = run_checker(report, allowlist)
    assert result.returncode == 1
    assert result.stdout.count("VIOLATION") == 2
