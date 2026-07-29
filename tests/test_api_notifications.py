"""API tests for notification settings / test / history and About."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_get_notification_settings(client: TestClient) -> None:
    response = client.get("/api/notifications/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["smtp_password_set"] is False
    assert "smtp_password" not in data


def test_update_notification_settings(client: TestClient) -> None:
    response = client.post(
        "/api/notifications/settings",
        json={
            "enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
            "smtp_from": "alerts@example.com",
            "smtp_to": "me@example.com",
            "cooldown_seconds": 600,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["settings"]["enabled"] is True
    assert data["settings"]["smtp_host"] == "smtp.example.com"
    assert data["settings"]["smtp_password_set"] is True
    assert data["settings"]["cooldown_seconds"] == 600


def test_test_email_records_history(client: TestClient) -> None:
    client.post(
        "/api/notifications/settings",
        json={
            "enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_from": "a@b.c",
            "smtp_to": "a@b.c",
        },
    )
    with patch("starpulse.services.notifications.send_smtp_email"):
        response = client.post("/api/notifications/test")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    history = client.get("/api/notifications/history")
    assert history.status_code == 200
    payload = history.json()
    assert payload["count"] >= 1
    assert payload["events"][0]["event_type"] == "test"


def test_about_endpoint(client: TestClient) -> None:
    response = client.get("/api/about")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "StarPulse"
    assert "version" in data
    assert "github_url" in data
    assert "credits" in data
    assert len(data["credits"]) >= 1
