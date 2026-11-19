"""SCIM 2.0 user provisioning tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr("app.routes.scim.SCIM_TOKEN", "test-scim-token")
    with TestClient(app) as test_client:
        yield test_client


def _auth():
    return {"Authorization": "Bearer test-scim-token"}


def test_scim_requires_token(client):
    assert client.get("/scim/v2/Users").status_code == 401
    assert client.get("/scim/v2/Users", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_scim_crud_lifecycle(client):
    # Create
    created = client.post(
        "/scim/v2/Users",
        json={"userName": "scim-user@example.edu", "displayName": "Scim User", "role": "student"},
        headers=_auth(),
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    assert created.json()["userName"] == "scim-user@example.edu"

    # Read
    fetched = client.get(f"/scim/v2/Users/{user_id}", headers=_auth())
    assert fetched.status_code == 200
    assert fetched.json()["displayName"] == "Scim User"

    # List with filter
    listed = client.get('/scim/v2/Users?filter=userName eq "scim-user@example.edu"', headers=_auth())
    assert listed.status_code == 200
    assert listed.json()["totalResults"] == 1

    # Duplicate
    dup = client.post("/scim/v2/Users", json={"userName": "scim-user@example.edu"}, headers=_auth())
    assert dup.status_code == 409

    # Patch role
    patched = client.patch(f"/scim/v2/Users/{user_id}", json={"role": "admin"}, headers=_auth())
    assert patched.status_code == 200
    assert patched.json()["role"] == "admin"

    # Deprovision via active=false
    deprov = client.patch(f"/scim/v2/Users/{user_id}", json={"active": False}, headers=_auth())
    assert deprov.status_code == 200

    assert client.get(f"/scim/v2/Users/{user_id}", headers=_auth()).status_code == 404


def test_scim_delete_returns_204(client):
    created = client.post("/scim/v2/Users", json={"userName": "to-delete@example.edu"}, headers=_auth())
    user_id = created.json()["id"]
    response = client.delete(f"/scim/v2/Users/{user_id}", headers=_auth())
    assert response.status_code == 204
    assert client.get(f"/scim/v2/Users/{user_id}", headers=_auth()).status_code == 404


def test_scim_disabled_without_token(monkeypatch):
    monkeypatch.setattr("app.routes.scim.SCIM_TOKEN", "")
    with TestClient(app) as c:
        assert c.get("/scim/v2/Users", headers={"Authorization": "Bearer x"}).status_code == 503