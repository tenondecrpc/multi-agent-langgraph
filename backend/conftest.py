# Root conftest.py - configures environment variables before any test collection.
# This file is loaded by pytest before any test modules are imported.
import os

os.environ.setdefault("BACKEND_ENCRYPTION_ACTIVE_KEY_ID", "test-key-001")
os.environ.setdefault(
    "BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY",
    "JMJFil3dNxg-vhMCYVebCtquYMmsmeIYu9qkZsWVlrU=",
)
os.environ.setdefault("BACKEND_WEBHOOK_SHARED_SECRET", "test-webhook-secret-for-testing")
