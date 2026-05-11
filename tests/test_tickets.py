"""
test_tickets.py — Integration tests for the tickets API.
Tests create, read, update, filter, and delete operations.

Run with:
    docker compose exec api pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.main import app

# Use an in-memory SQLite DB for tests (no SQL Server required for unit tests)
TEST_DB_URL = "sqlite:///./test_supportops.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_ticket(client):
    resp = client.post("/tickets", json={
        "title": "Test ticket for unit tests",
        "description": "Created by pytest",
        "priority": "medium",
        "category": "software",
        "reporter": "test_runner",
    })
    assert resp.status_code == 201
    return resp.json()


# ── CREATE ────────────────────────────────────────────────────────────────────

class TestCreateTicket:
    def test_create_valid_ticket(self, client):
        resp = client.post("/tickets", json={
            "title": "Printer offline on floor 2",
            "priority": "high",
            "category": "hardware",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert data["status"] == "open"
        assert data["source"] == "manual"
        assert data["escalated"] is False

    def test_create_ticket_with_all_fields(self, client):
        resp = client.post("/tickets", json={
            "title": "VPN down for entire office",
            "description": "All users affected since 9am",
            "priority": "critical",
            "category": "network",
            "assignee": "network.team",
            "reporter": "sysadmin1",
            "source": "auto",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["assignee"] == "network.team"
        assert data["source"] == "auto"

    def test_create_ticket_title_too_short(self, client):
        resp = client.post("/tickets", json={"title": "Hi"})
        assert resp.status_code == 422  # Validation error

    def test_create_ticket_invalid_priority(self, client):
        resp = client.post("/tickets", json={
            "title": "Valid title here",
            "priority": "super_urgent",  # Not a valid enum value
        })
        assert resp.status_code == 422


# ── READ ──────────────────────────────────────────────────────────────────────

class TestReadTickets:
    def test_list_tickets_empty(self, client):
        resp = client.get("/tickets")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tickets_returns_created(self, client, sample_ticket):
        resp = client.get("/tickets")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_ticket_by_id(self, client, sample_ticket):
        tid = sample_ticket["id"]
        resp = client.get(f"/tickets/{tid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tid

    def test_get_nonexistent_ticket(self, client):
        resp = client.get("/tickets/99999")
        assert resp.status_code == 404

    def test_filter_by_status(self, client, sample_ticket):
        resp = client.get("/tickets?status=open")
        assert resp.status_code == 200
        assert all(t["status"] == "open" for t in resp.json())

    def test_filter_by_priority(self, client):
        client.post("/tickets", json={"title": "Critical network outage now", "priority": "critical"})
        client.post("/tickets", json={"title": "Low priority cleanup task", "priority": "low"})

        resp = client.get("/tickets?priority=critical")
        assert resp.status_code == 200
        assert all(t["priority"] == "critical" for t in resp.json())


# ── UPDATE ────────────────────────────────────────────────────────────────────

class TestUpdateTicket:
    def test_update_status(self, client, sample_ticket):
        tid = sample_ticket["id"]
        resp = client.patch(f"/tickets/{tid}", json={"status": "in_progress"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_resolve_ticket_sets_resolved_at(self, client, sample_ticket):
        tid = sample_ticket["id"]
        resp = client.patch(f"/tickets/{tid}", json={"status": "resolved"})
        assert resp.status_code == 200
        assert resp.json()["resolved_at"] is not None

    def test_update_assignee(self, client, sample_ticket):
        tid = sample_ticket["id"]
        resp = client.patch(f"/tickets/{tid}", json={"assignee": "john.doe"})
        assert resp.status_code == 200
        assert resp.json()["assignee"] == "john.doe"

    def test_update_nonexistent_ticket(self, client):
        resp = client.patch("/tickets/99999", json={"status": "resolved"})
        assert resp.status_code == 404


# ── DELETE ────────────────────────────────────────────────────────────────────

class TestDeleteTicket:
    def test_delete_ticket(self, client, sample_ticket):
        tid = sample_ticket["id"]
        resp = client.delete(f"/tickets/{tid}")
        assert resp.status_code == 204

        # Confirm it's gone
        resp = client.get(f"/tickets/{tid}")
        assert resp.status_code == 404

    def test_delete_nonexistent_ticket(self, client):
        resp = client.delete("/tickets/99999")
        assert resp.status_code == 404
