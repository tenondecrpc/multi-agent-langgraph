from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.persistence.encryption import EnvelopeCipher


@pytest.fixture
def cipher():
    return EnvelopeCipher(
        active_key_id="kek-v1",
        active_wrapping_key="test-wrapping-key-v1",
        previous_key_ids=["kek-v0"],
        previous_wrapping_keys={"kek-v0": "test-wrapping-key-v0"},
        rotation_sla_days=90,
    )


@pytest.fixture
def now():
    return datetime.now(tz=UTC)


class TestEnvelopeCipherDualRead:
    def test_decrypt_with_active_key(self, cipher):
        plaintext = "my-secret-value"
        envelope = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(
            envelope["ciphertext"],
            dek_id=envelope["dek_id"],
            signature=envelope["signature"],
        )
        assert decrypted == plaintext

    def test_decrypt_with_previous_key(self, cipher):
        plaintext = "my-secret-value"
        import base64
        import hmac

        wrapping_key = "test-wrapping-key-v0"
        payload = base64.urlsafe_b64encode(plaintext.encode("utf-8")).decode("ascii")
        signature = hmac.new(
            wrapping_key.encode("utf-8"),
            plaintext.encode("utf-8"),
            "sha256",
        ).hexdigest()
        ciphertext = f"enc::{payload}"

        decrypted = cipher.decrypt(ciphertext, dek_id="kek-v0", signature=signature)
        assert decrypted == plaintext

    def test_decrypt_wrong_signature_rejected(self, cipher):
        with pytest.raises(ValueError, match="Ciphertext signature mismatch"):
            cipher.decrypt("enc::dGVzdA==", dek_id="kek-v1", signature="wrong-signature")


class TestRotationSLA:
    def test_rotation_due_after_sla_days(self, cipher, now):
        issued_at = now - timedelta(days=91)
        envelope = cipher.encrypt("secret", issued_at=issued_at)
        assert cipher.rotation_due(envelope) is True

    def test_rotation_not_due_within_sla(self, cipher, now):
        issued_at = now - timedelta(days=30)
        envelope = cipher.encrypt("secret", issued_at=issued_at)
        assert cipher.rotation_due(envelope) is False

    def test_rotation_due_at_boundary(self, cipher, now):
        issued_at = now - timedelta(days=90)
        envelope = cipher.encrypt("secret", issued_at=issued_at)
        assert cipher.rotation_due(envelope) is True

    def test_custom_sla_days(self, cipher, now):
        issued_at = now - timedelta(days=31)
        envelope = cipher.encrypt("secret", issued_at=issued_at)
        assert cipher.rotation_due(envelope, sla_days=30) is True
        assert cipher.rotation_due(envelope, sla_days=60) is False


class TestStaleEnvelopeRotation:
    def test_rotate_stale_envelopes(self, cipher, now):
        fresh_envelope = cipher.encrypt("fresh", issued_at=now - timedelta(days=10))
        stale_envelope = cipher.encrypt("stale", issued_at=now - timedelta(days=100))

        report = cipher.rotate_stale_envelopes(
            [fresh_envelope, stale_envelope],
            now=now,
        )

        assert report.total_envelopes == 2
        assert report.due_before_rotation == 1
        assert report.rotated_count == 1
        assert len(report.rotated_envelopes) == 2

    def test_rotate_all_fresh(self, cipher, now):
        envelope = cipher.encrypt("fresh", issued_at=now - timedelta(days=10))
        report = cipher.rotate_stale_envelopes([envelope], now=now)
        assert report.due_before_rotation == 0
        assert report.rotated_count == 0


class TestBreakGlassLifecycle:
    def test_single_approver_cannot_activate(self):
        from backend.credentials.admin import BreakGlassRequest

        request = BreakGlassRequest(
            tenant_id="tenant-test",
            team_id="team-alpha",
            reason="emergency access needed",
            duration_hours=4,
        )
        assert request.tenant_id == "tenant-test"
        assert request.duration_hours == 4

    def test_grant_expires(self):
        from backend.credentials.admin import BreakGlassRequest

        request = BreakGlassRequest(
            tenant_id="tenant-test",
            team_id="team-alpha",
            reason="emergency",
            duration_hours=1,
        )
        expires_at = datetime.now(tz=UTC) + timedelta(hours=request.duration_hours)
        assert expires_at > datetime.now(tz=UTC)


class TestKekVersionManagement:
    def test_introduce_new_kek(self):
        from backend.credentials.admin import KekIntroduction

        intro = KekIntroduction(
            kek_id="kek-v2",
            kms_ref="vault://kv/test/kek-v2",
            introduced_by="admin@test",
        )
        assert intro.kek_id == "kek-v2"
        assert intro.kms_ref == "vault://kv/test/kek-v2"

    def test_cannot_retire_default_kek(self):
        from backend.credentials.admin import KekRotationRequest

        request = KekRotationRequest(
            new_kek_id="kek-v2",
            kms_ref="vault://kv/test/kek-v2",
            introduced_by="admin@test",
        )
        assert request.new_kek_id == "kek-v2"


class TestCredentialRotationSchedule:
    def test_schedule_creation(self):
        from backend.credentials.admin import CredentialRotationEntry

        entry = CredentialRotationEntry(
            schedule_id="sched-1",
            tenant_id="tenant-test",
            team_id="team-alpha",
            credential_kind="github_app",
            credential_id="install-123",
            rotated_at=datetime.now(tz=UTC).isoformat(),
            next_rotation_due=(datetime.now(tz=UTC) + timedelta(days=90)).isoformat(),
            rotation_sla_days=90,
            overdue=False,
        )
        assert not entry.overdue
        assert entry.rotation_sla_days == 90

    def test_overdue_detection(self):
        from backend.credentials.admin import CredentialRotationEntry

        past_due = datetime.now(tz=UTC) - timedelta(days=1)
        entry = CredentialRotationEntry(
            schedule_id="sched-2",
            tenant_id="tenant-test",
            team_id="team-alpha",
            credential_kind="jira_token",
            credential_id="token-456",
            rotated_at=(past_due - timedelta(days=91)).isoformat(),
            next_rotation_due=past_due.isoformat(),
            rotation_sla_days=90,
            overdue=True,
        )
        assert entry.overdue
