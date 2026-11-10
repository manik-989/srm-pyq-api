"""Unit tests for configuration, URL helpers, and pagination branches."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from postgrest.exceptions import APIError

import api_server
from tests.fakes import FakeSupabase

COURSE: dict[str, Any] = {
    "id": "course-1",
    "course_code": "21CSE101",
    "course_name": "Programming in C",
}

PAPER: dict[str, Any] = {
    "id": "paper-1",
    "course_id": "course-1",
    "source_item_url": "https://example.com/paper-1.pdf",
}


def install_fake(monkeypatch: pytest.MonkeyPatch, resolver: Any) -> FakeSupabase:
    fake = FakeSupabase(resolver)
    monkeypatch.setattr(api_server, "supabase", fake)
    return fake


def test_load_env_file_reads_quoted_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYQ_TEST_VALUE", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\n\nPYQ_TEST_VALUE="quoted value"\nIGNORED_LINE\n',
        encoding="utf-8",
    )

    api_server.load_env_file(env_file)

    assert os.environ["PYQ_TEST_VALUE"] == "quoted value"
    monkeypatch.delenv("PYQ_TEST_VALUE")


def test_load_env_file_ignores_missing_file(tmp_path: Path) -> None:
    api_server.load_env_file(tmp_path / "missing.env")


def test_load_env_file_does_not_override_existing_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYQ_TEST_EXISTING", "keep")
    env_file = tmp_path / ".env"
    env_file.write_text("PYQ_TEST_EXISTING=replace\n", encoding="utf-8")

    api_server.load_env_file(env_file)

    assert os.environ["PYQ_TEST_EXISTING"] == "keep"


def test_get_env_list_splits_and_trims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYQ_TEST_LIST", " a, b ,,c ")
    assert api_server.get_env_list("PYQ_TEST_LIST") == ["a", "b", "c"]

    monkeypatch.delenv("PYQ_TEST_LIST")
    assert api_server.get_env_list("PYQ_TEST_LIST") == []


def test_normalize_metadata_handles_invalid_input() -> None:
    assert api_server.normalize_metadata(None) is None
    assert api_server.normalize_metadata("not-a-dict") is None

    result = api_server.normalize_metadata({"semester": "3", "exam_year": 2024})

    assert result == {"exam_month": None, "exam_year": 2024, "semester": None, "page_found": None}


def test_derive_public_url_only_handles_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://files.example.com/")

    assert api_server.derive_public_url({"storage_provider": "s3", "object_key": "a.pdf"}) == ""
    assert api_server.derive_public_url({"storage_provider": "r2", "object_key": ""}) == ""
    assert (
        api_server.derive_public_url({"storage_provider": "r2", "object_key": "/papers/a b.pdf"})
        == "https://files.example.com/papers/a%20b.pdf"
    )


def test_with_computed_public_url_prefers_stored_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://files.example.com")

    row = api_server.with_computed_public_url({"public_url": "https://stored.example.com/a.pdf", "object_key": "a.pdf"})

    assert row["public_url"] == "https://stored.example.com/a.pdf"


def test_get_r2_client_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "R2_ENDPOINT_URL",
        "CLOUDFLARER2_S3_API",
        "CLOUDFLARE_ENDPOINTS",
        "R2_ACCESS_KEY_ID",
        "CLOUDFLARE_ACCESS_KEY",
        "R2_SECRET_ACCESS_KEY",
        "CLOUDFLARE_SECRET_ACCESS_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="Missing R2 credentials"):
        api_server.get_r2_client()


def test_get_r2_client_builds_s3_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-key")

    client = api_server.get_r2_client()

    assert client.meta.endpoint_url == "https://account.r2.cloudflarestorage.com"


def test_list_courses_uses_cursor(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = install_fake(monkeypatch, lambda table, calls: [COURSE])

    response = client.get("/v1/courses", params={"cursor": "21CSE100"})

    assert response.status_code == 200
    assert ("gt", "course_code", "21CSE100") in fake.queries[0].calls


def test_list_courses_falls_back_when_abbreviation_column_is_missing(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = {"executions": 0}

    def resolver(table: str, calls: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        state["executions"] += 1
        if state["executions"] == 1:
            raise APIError({"message": "column does not exist", "code": "42703"})
        return [COURSE]

    fake = install_fake(monkeypatch, resolver)

    response = client.get("/v1/courses", params={"q": "CSE"})

    assert response.status_code == 200
    assert len(fake.queries) == 2
    fallback_filter = next(value for name, *rest in fake.queries[1].calls if name == "or_" for value in rest)
    assert "course_abbreviation" not in fallback_filter


def test_list_course_papers_uses_cursor(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def resolver(table: str, calls: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        return [COURSE] if table == "courses" else [PAPER]

    fake = install_fake(monkeypatch, resolver)

    response = client.get("/v1/courses/21CSE101/papers", params={"cursor": "https://example.com/prev"})

    assert response.status_code == 200
    assert ("gt", "source_item_url", "https://example.com/prev") in fake.queries[1].calls


def test_get_paper_without_course_returns_null_course(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def resolver(table: str, calls: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        return [PAPER] if table == "papers" else []

    install_fake(monkeypatch, resolver)

    response = client.get("/v1/papers/paper-1")

    assert response.status_code == 200
    assert response.json()["data"]["course"] is None


def test_fallback_exception_handler_returns_json_500() -> None:
    response = api_server.fallback_exception_handler(None, RuntimeError("boom"))

    assert response.status_code == 500
    assert response.body == b'{"error":{"code":"INTERNAL_ERROR","message":"boom"}}'
