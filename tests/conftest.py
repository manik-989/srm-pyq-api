"""Shared pytest fixtures for the SRM PYQ API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# api_server validates credentials at import time, so provide safe test values
# before the module is imported by the test suite.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.pop("R2_PUBLIC_BASE_URL", None)
os.environ.pop("R2_PUBLIC_URL", None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api_server  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(api_server.app)
