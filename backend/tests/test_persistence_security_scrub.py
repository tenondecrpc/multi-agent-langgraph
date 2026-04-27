from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.persistence.encryption import EnvelopeCipher
from backend.persistence.factory import build_in_memory_persistence
from backend.worker import process_encryption_key_rotation

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "backend" / "src" / "backend"
FORBIDDEN_LOG_TOKENS = {
    "password",
    "secret",
    "api_key",
    "private_key",
    "ciphertext",
    "wrapping_key",
}


def test_envelope_cipher_can_rotate_and_scrub_secret_payloads() -> None:
    from cryptography.fernet import Fernet

    cipher = EnvelopeCipher(
        provider="vault",
        configured=True,
        active_key_id="kek-v2",
        active_fernet_key=Fernet.generate_key().decode(),
        previous_key_ids=["kek-v1"],
        previous_fernet_keys={"kek-v1": Fernet.generate_key().decode()},
    )

    first = cipher.encrypt("super-secret")
    rotated = cipher.rotate_ciphertext(
        first["ciphertext"],
        dek_id=first["dek_id"],
    )
    scrubbed = cipher.scrub_payload(
        {
            "api_token": "plaintext",
            "nested": {"ciphertext": rotated["ciphertext"]},
        }
    )

    assert cipher.decrypt(first["ciphertext"], dek_id=first["dek_id"]) == "super-secret"
    assert rotated["dek_id"] == "kek-v2"
    assert scrubbed["api_token"] == "***redacted***"
    assert scrubbed["nested"]["ciphertext"] == "***redacted***"
    assert cipher.decrypt(
        rotated["ciphertext"],
        dek_id=rotated["dek_id"],
    ) == "super-secret"


def test_encryption_rotation_job_rewraps_stale_envelopes_and_updates_sla_metrics() -> None:
    from cryptography.fernet import Fernet

    persistence = build_in_memory_persistence()
    persistence.encryption = EnvelopeCipher(
        provider="vault",
        configured=True,
        active_key_id="kek-v2",
        active_fernet_key=Fernet.generate_key().decode(),
        previous_key_ids=["kek-v1"],
        previous_fernet_keys={"kek-v1": Fernet.generate_key().decode()},
        rotation_sla_days=30,
    )
    stale = EnvelopeCipher(
        provider="vault",
        configured=True,
        active_key_id="kek-v1",
        active_fernet_key=persistence.encryption.previous_fernet_keys["kek-v1"],
    ).encrypt(
        "expired-secret",
        issued_at=datetime.now(tz=UTC) - timedelta(days=31),
    )

    rotated = process_encryption_key_rotation([stale], persistence=persistence)

    assert rotated[0]["dek_id"] == "kek-v2"
    assert persistence.encryption.decrypt(
        rotated[0]["ciphertext"],
        dek_id=rotated[0]["dek_id"],
    ) == "expired-secret"
    metrics = persistence.telemetry.render_prometheus()
    assert "devsquad_encryption_rotation_due_total 1.0" in metrics


def test_logging_calls_do_not_reference_secret_or_ciphertext_fields() -> None:
    violations: list[str] = []

    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _call_name(node.func)
            if call_name not in {"info", "warning", "error", "exception", "debug"}:
                continue
            tokens = " ".join(_string_literals(node)).lower()
            if any(token in tokens for token in FORBIDDEN_LOG_TOKENS):
                violations.append(f"{path.relative_to(SRC_ROOT)}:{node.lineno}")

    assert violations == []


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _string_literals(node: ast.Call) -> list[str]:
    values: list[str] = []
    for inner in ast.walk(node):
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            values.append(inner.value)
    return values
