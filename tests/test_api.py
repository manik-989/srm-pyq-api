"""Contract tests for the SRM PYQ API.

The Supabase client is replaced with an in-memory fake so the suite runs
without credentials or network access.
"""

from __future__ import annotations

from typing import Any

import pytest

import api_server
from tests.fakes import FakeSupabase

COURSE: dict[str, Any] = {
    "id": "course-1",
    "course_code": "21CSE101",
    "course_name": "Programming in C",
    "department": "CSE",
    "program": "B.Tech",
    "semester": 3,
    "is_active": True,
}

PAPER: dict[str, Any] = {
    "id": "paper-1",
    "course_id": "course-1",
    "title": "End Semester 2024",
    "exam_year": 2024,
    "exam_month": 5,
    "exam_term": "FALL",
    "session_label": "Fall 2024",
    "source_subject_url": "https://example.com/subject",
    "source_item_url": "https://example.com/paper-1.pdf",
    "publisher": "SRM",
    "created_at": "2024-06-01T00:00:00Z",
}

FILE: dict[str, Any] = {
    "id": "file-1",
    "paper_id": "paper-1",
    "storage_provider": "r2",
    "bucket": "pyq-files",
    "object_key": "papers/2024/end sem.pdf",
    "source_pdf_url": "https://example.com/paper-1.pdf",
    "public_url": None,
    "mime_type": "application/pdf",
    "size_bytes": 1234,
    "sha256": "abc123",
    "is_primary": True,
    "created_at": "2024-06-01T00:00:00Z",
}


def install_fake(monkeypatch: pytest.MonkeyPatch, resolver: Any) -> FakeSupabase:
    fake = FakeSupabase(resolver)
    monkeypatch.setattr(api_server, "supabase", fake)
    return fake


def test_health_returns_service_metadata(client: Any) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "srm-pyq-api"
    assert body["version"] == api_server.SERVICE_VERSION


def test_metrics_endpoint_exposes_prometheus_format(client: Any) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "python_info" in response.text


def test_request_id_is_echoed(client: Any) -> None:
    response = client.get("/health", headers={"x-request-id": "req-123"})

    assert response.headers["x-request-id"] == "req-123"


def test_ready_reports_ok_when_database_is_reachable(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, lambda table, calls: [])

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_ready_returns_503_when_database_fails(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def resolver(table: str, calls: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        raise RuntimeError("database offline")

    install_fake(monkeypatch, resolver)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not ready"


def test_list_courses_returns_cursor_page(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{**COURSE, "course_code": f"21CSE10{i}"} for i in range(3)]
    fake = install_fake(monkeypatch, lambda table, calls: rows)

    response = client.get("/v1/courses", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["page"] == {"has_more": True, "next_cursor": "21CSE101", "limit": 2}
    assert ("limit", 3) in fake.queries[0].calls


def test_list_courses_search_uses_all_searchable_columns(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = install_fake(monkeypatch, lambda table, calls: [COURSE])

    response = client.get("/v1/courses", params={"q": "CSE,101", "limit": 1})

    assert response.status_code == 200
    calls = fake.queries[0].calls
    search = next(value for name, *rest in calls if name == "or_" for value in rest)
    assert "course_code.ilike.%CSE 101%" in search
    assert "course_name.ilike.%CSE 101%" in search
    assert "course_abbreviation.ilike.%CSE 101%" in search


def test_get_course_returns_course(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, lambda table, calls: [COURSE])

    response = client.get("/v1/courses/21CSE101")

    assert response.status_code == 200
    assert response.json()["data"]["course_code"] == "21CSE101"


def test_get_course_returns_404(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, lambda table, calls: [])

    response = client.get("/v1/courses/DOES-NOT-EXIST")

    assert response.status_code == 404
    assert "Course not found" in response.json()["detail"]


def test_list_course_papers_applies_filters(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def resolver(table: str, calls: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        return [COURSE] if table == "courses" else [PAPER]

    fake = install_fake(monkeypatch, resolver)

    response = client.get(
        "/v1/courses/21CSE101/papers",
        params={"year": 2024, "term": "FALL", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["course"]["course_code"] == "21CSE101"
    assert body["data"][0]["id"] == "paper-1"
    assert body["page"]["has_more"] is False

    paper_calls = fake.queries[1].calls
    assert ("eq", "exam_year", 2024) in paper_calls
    assert ("eq", "exam_term", "FALL") in paper_calls


def test_get_paper_normalizes_metadata(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    paper = {**PAPER, "metadata_json": {"exam_month": 5, "exam_year": 2024, "semester": 3, "page_found": 2}}

    def resolver(table: str, calls: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        return [paper] if table == "papers" else [COURSE]

    install_fake(monkeypatch, resolver)

    response = client.get("/v1/papers/paper-1")

    assert response.status_code == 200
    data = response.json()["data"]
    assert "metadata_json" not in data
    assert data["metadata"] == {"exam_month": 5, "exam_year": 2024, "semester": [3], "page_found": 2}
    assert data["course"]["id"] == "course-1"


def test_get_paper_returns_404(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, lambda table, calls: [])

    response = client.get("/v1/papers/missing")

    assert response.status_code == 404
    assert "Paper not found" in response.json()["detail"]


def test_list_paper_files_computes_public_url(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://files.example.com/")
    install_fake(monkeypatch, lambda table, calls: [FILE])

    response = client.get("/v1/papers/paper-1/files")

    assert response.status_code == 200
    assert response.json()["data"][0]["public_url"] == ("https://files.example.com/papers/2024/end%20sem.pdf")


def test_download_prefers_public_url(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://files.example.com")
    install_fake(monkeypatch, lambda table, calls: [FILE])

    response = client.get("/v1/files/file-1/download")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["url_type"] == "public"
    assert body["expires_in"] is None
    assert body["download_url"].startswith("https://files.example.com/")


def test_download_falls_back_to_signed_url(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeR2:
        def generate_presigned_url(self, **kwargs: Any) -> str:
            assert kwargs["ClientMethod"] == "get_object"
            assert kwargs["ExpiresIn"] == 900
            return "https://signed.example.com/file"

    monkeypatch.setattr(api_server, "get_r2_client", lambda: FakeR2())
    install_fake(monkeypatch, lambda table, calls: [FILE])

    response = client.get("/v1/files/file-1/download")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["url_type"] == "signed"
    assert body["expires_in"] == 900
    assert body["download_url"] == "https://signed.example.com/file"


def test_download_returns_500_when_signing_fails(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_client() -> Any:
        raise RuntimeError("missing credentials")

    monkeypatch.setattr(api_server, "get_r2_client", broken_client)
    install_fake(monkeypatch, lambda table, calls: [FILE])

    response = client.get("/v1/files/file-1/download")

    assert response.status_code == 500
    assert "Could not generate signed URL" in response.json()["detail"]


def test_download_validates_ttl(client: Any) -> None:
    response = client.get("/v1/files/file-1/download", params={"ttl_seconds": 30})

    assert response.status_code == 422


def test_download_returns_404(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, lambda table, calls: [])

    response = client.get("/v1/files/missing/download")

    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]
