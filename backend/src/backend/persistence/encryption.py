from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel


class EnvelopeRotationReport(BaseModel):
    total_envelopes: int
    due_before_rotation: int
    rotated_count: int
    rotated_envelopes: list[dict[str, str]]


class EnvelopeCipher(BaseModel):
    provider: str = "vault"
    configured: bool = False
    active_key_id: str = "unset"
    active_wrapping_key: str = "development-wrapping-key"
    master_key_reference: str = "vault://kv/langgraph-dev-squad/runtime#wrapping-key"
    previous_key_ids: list[str] = []
    previous_wrapping_keys: dict[str, str] = {}
    rotation_sla_days: int = 30

    @classmethod
    def from_env(cls) -> EnvelopeCipher:
        provider = os.getenv("BACKEND_ENCRYPTION_PROVIDER", "vault")
        active_key_id = os.getenv("BACKEND_ENCRYPTION_ACTIVE_KEY_ID", "unset")
        active_wrapping_key = os.getenv(
            "BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY",
            "development-wrapping-key",
        )
        previous_key_ids = [
            item.strip()
            for item in os.getenv("BACKEND_ENCRYPTION_PREVIOUS_KEY_IDS", "").split(",")
            if item.strip()
        ]
        default_reference = (
            os.getenv("BACKEND_ENCRYPTION_VAULT_KEY_PATH")
            or os.getenv("BACKEND_ENCRYPTION_KMS_KEY_ARN")
            or "vault://kv/langgraph-dev-squad/runtime#wrapping-key"
        )
        previous_wrapping_keys: dict[str, str] = {}
        for key_id in previous_key_ids:
            env_key = f"BACKEND_ENCRYPTION_WRAPPING_KEY_{key_id.upper().replace('-', '_')}"
            previous_wrapping_keys[key_id] = os.getenv(env_key, active_wrapping_key)
        return cls(
            provider=provider,
            configured=active_key_id != "unset",
            active_key_id=active_key_id,
            active_wrapping_key=active_wrapping_key,
            master_key_reference=os.getenv("BACKEND_ENCRYPTION_MASTER_KEY_REF", default_reference),
            previous_key_ids=previous_key_ids,
            previous_wrapping_keys=previous_wrapping_keys,
            rotation_sla_days=int(os.getenv("BACKEND_ENCRYPTION_ROTATION_SLA_DAYS", "30")),
        )

    def encrypt(self, plaintext: str, *, issued_at: datetime | None = None) -> dict[str, str]:
        created_at = (issued_at or datetime.now(tz=UTC)).astimezone(UTC)
        nonce = hashlib.sha256(f"{self.active_key_id}:{plaintext}".encode()).hexdigest()[:24]
        signature = hmac.new(
            self.active_wrapping_key.encode("utf-8"),
            plaintext.encode("utf-8"),
            "sha256",
        ).hexdigest()
        payload = base64.urlsafe_b64encode(plaintext.encode("utf-8")).decode("ascii")
        return {
            "ciphertext": f"enc::{payload}",
            "dek_id": self.active_key_id,
            "nonce": nonce,
            "signature": signature,
            "issued_at": created_at.isoformat(),
        }

    def decrypt(self, ciphertext: str, *, dek_id: str, signature: str) -> str:
        wrapping_key = self._resolve_wrapping_key(dek_id)
        encoded = ciphertext.removeprefix("enc::")
        plaintext = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
        expected = hmac.new(
            wrapping_key.encode("utf-8"),
            plaintext.encode("utf-8"),
            "sha256",
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Ciphertext signature mismatch.")
        return plaintext

    def rotate_ciphertext(self, ciphertext: str, *, dek_id: str, signature: str) -> dict[str, str]:
        plaintext = self.decrypt(ciphertext, dek_id=dek_id, signature=signature)
        return self.encrypt(plaintext)

    def rotation_due(
        self,
        envelope: dict[str, str],
        *,
        now: datetime | None = None,
        sla_days: int | None = None,
    ) -> bool:
        issued_at_raw = envelope.get("issued_at")
        if not issued_at_raw:
            return True
        issued_at = datetime.fromisoformat(issued_at_raw)
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=UTC)
        deadline = issued_at.astimezone(UTC) + timedelta(days=sla_days or self.rotation_sla_days)
        return (now or datetime.now(tz=UTC)).astimezone(UTC) >= deadline

    def rotate_stale_envelopes(
        self,
        envelopes: list[dict[str, str]],
        *,
        now: datetime | None = None,
        sla_days: int | None = None,
    ) -> EnvelopeRotationReport:
        rotated: list[dict[str, str]] = []
        due_before_rotation = 0
        reference_time = now or datetime.now(tz=UTC)
        for envelope in envelopes:
            if self.rotation_due(envelope, now=reference_time, sla_days=sla_days):
                due_before_rotation += 1
                rotated.append(
                    self.rotate_ciphertext(
                        envelope["ciphertext"],
                        dek_id=envelope["dek_id"],
                        signature=envelope["signature"],
                    )
                )
            else:
                rotated.append(dict(envelope))
        return EnvelopeRotationReport(
            total_envelopes=len(envelopes),
            due_before_rotation=due_before_rotation,
            rotated_count=due_before_rotation,
            rotated_envelopes=rotated,
        )

    def scrub_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            scrubbed: dict[str, Any] = {}
            for key, value in payload.items():
                if _looks_secret(key):
                    scrubbed[key] = "***redacted***"
                else:
                    scrubbed[key] = self.scrub_payload(value)
            return scrubbed
        if isinstance(payload, list):
            return [self.scrub_payload(item) for item in payload]
        if isinstance(payload, str):
            if payload.startswith("enc::") or payload.startswith("ciphertext:"):
                return "***redacted***"
            return payload
        return payload

    def encrypt_placeholder(self, plaintext: str) -> str:
        return self.encrypt(plaintext)["ciphertext"]

    def decrypt_placeholder(self, ciphertext: str) -> str:
        try:
            payload = json.loads(ciphertext)
        except json.JSONDecodeError:
            return ciphertext.removeprefix("enc::")
        return self.decrypt(
            payload["ciphertext"],
            dek_id=payload["dek_id"],
            signature=payload["signature"],
        )

    def _resolve_wrapping_key(self, key_id: str) -> str:
        if key_id == self.active_key_id:
            return self.active_wrapping_key
        return self.previous_wrapping_keys.get(key_id, self.active_wrapping_key)


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered
        for token in ("secret", "token", "password", "key", "ciphertext", "nonce", "dek")
    )
