from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet
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
    active_fernet_key: str = ""
    master_key_reference: str = "vault://kv/langgraph-dev-squad/runtime#wrapping-key"
    previous_key_ids: list[str] = []
    previous_fernet_keys: dict[str, str] = {}
    rotation_sla_days: int = 30

    model_config = {"extra": "forbid"}

    @classmethod
    def from_env(cls) -> EnvelopeCipher:
        provider = os.getenv("BACKEND_ENCRYPTION_PROVIDER", "vault")
        active_key_id = os.getenv("BACKEND_ENCRYPTION_ACTIVE_KEY_ID", "")
        active_fernet_key = os.getenv("BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY", "")
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
        previous_fernet_keys: dict[str, str] = {}
        for key_id in previous_key_ids:
            env_key = f"BACKEND_ENCRYPTION_WRAPPING_KEY_{key_id.upper().replace('-', '_')}"
            key_value = os.getenv(env_key, "")
            if key_value:
                previous_fernet_keys[key_id] = key_value

        configured = bool(active_key_id and active_fernet_key and active_key_id != "unset")

        return cls(
            provider=provider,
            configured=configured,
            active_key_id=active_key_id if active_key_id else "unset",
            active_fernet_key=active_fernet_key,
            master_key_reference=os.getenv("BACKEND_ENCRYPTION_MASTER_KEY_REF", default_reference),
            previous_key_ids=previous_key_ids,
            previous_fernet_keys=previous_fernet_keys,
            rotation_sla_days=int(os.getenv("BACKEND_ENCRYPTION_ROTATION_SLA_DAYS", "30")),
        )

    def model_post_init(self, __context) -> None:
        if not self.configured:
            if self.active_key_id != "unset" and self.active_fernet_key:
                object.__setattr__(self, "configured", True)

    def encrypt(self, plaintext: str, *, issued_at: datetime | None = None) -> dict[str, str]:
        if not self.configured:
            raise RuntimeError(
                "EnvelopeCipher is not configured. Set BACKEND_ENCRYPTION_ACTIVE_KEY_ID "
                "and BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY environment variables."
            )
        fernet = Fernet(self.active_fernet_key.encode("utf-8"))
        created_at = (issued_at or datetime.now(tz=UTC)).astimezone(UTC)
        ciphertext_bytes = fernet.encrypt(plaintext.encode("utf-8"))
        ciphertext = ciphertext_bytes.decode("utf-8")
        return {
            "ciphertext": f"v2::{ciphertext}",
            "dek_id": self.active_key_id,
            "issued_at": created_at.isoformat(),
        }

    def decrypt(self, ciphertext: str, *, dek_id: str, signature: str = "") -> str:
        fernet_key = self._resolve_fernet_key(dek_id)

        if ciphertext.startswith("v2::"):
            raw_ciphertext = ciphertext.removeprefix("v2::")
            fernet = Fernet(fernet_key.encode("utf-8"))
            return fernet.decrypt(raw_ciphertext.encode("utf-8")).decode("utf-8")

        if ciphertext.startswith("enc::"):
            encoded = ciphertext.removeprefix("enc::")
            import base64
            return base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")

        raise ValueError(f"Unknown ciphertext format: {ciphertext[:20]}...")

    def rotate_ciphertext(self, ciphertext: str, *, dek_id: str, signature: str = "") -> dict[str, str]:
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
            if payload.startswith("v2::") or payload.startswith("enc::") or payload.startswith("ciphertext:"):
                return "***redacted***"
            return payload
        return payload

    def encrypt_placeholder(self, plaintext: str) -> str:
        return self.encrypt(plaintext)["ciphertext"]

    def decrypt_placeholder(self, ciphertext: str) -> str:
        try:
            payload = json.loads(ciphertext)
        except json.JSONDecodeError:
            return self.decrypt(ciphertext, dek_id=self.active_key_id)
        return self.decrypt(
            payload["ciphertext"],
            dek_id=payload["dek_id"],
        )

    def _resolve_fernet_key(self, key_id: str) -> str:
        if key_id == self.active_key_id:
            return self.active_fernet_key
        if key_id in self.previous_fernet_keys:
            return self.previous_fernet_keys[key_id]
        raise ValueError(f"No wrapping key found for key_id: {key_id}")


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered
        for token in ("secret", "token", "password", "ciphertext", "nonce", "dek")
    )
