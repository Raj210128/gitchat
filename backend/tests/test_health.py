"""
Basic smoke tests — no external services required.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_openapi_schema_accessible():
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/v1/ingest" in schema["paths"]
    assert "/api/v1/chat" in schema["paths"]


def test_ingest_validation_rejects_non_github_url():
    response = client.post(
        "/api/v1/ingest",
        json={"repo_url": "https://gitlab.com/user/repo", "branch": "main"},
    )
    assert response.status_code == 422


def test_ingest_validation_rejects_missing_url():
    response = client.post("/api/v1/ingest", json={"branch": "main"})
    assert response.status_code == 422
