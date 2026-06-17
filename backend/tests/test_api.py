from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_session_starts_ingesting() -> None:
    with patch("backend.agents.ingestion.run_ingestion"):
        response = client.post(
            "/sessions",
            json={"paper_url": "https://arxiv.org/abs/1706.03762"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ingesting"
    assert data["paper_url"] == "https://arxiv.org/abs/1706.03762"