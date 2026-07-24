"""API tests for auth and ownership scoping."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_register_and_login(api_client):
    resp = api_client.post(
        reverse("v1:register"),
        {"email": "new@example.com", "password": "secret123", "full_name": "New"},
        format="json",
    )
    assert resp.status_code == 201

    resp = api_client.post(
        reverse("v1:login"),
        {"email": "new@example.com", "password": "secret123"},
        format="json",
    )
    assert resp.status_code == 200
    assert "access" in resp.data
    assert resp.data["user"]["email"] == "new@example.com"


@pytest.mark.django_db
def test_duplicate_email_rejected(api_client, user):
    resp = api_client.post(
        reverse("v1:register"),
        {"email": user.email, "password": "secret123"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_orders_require_auth(api_client):
    resp = api_client.get(reverse("v1:order-list"))
    assert resp.status_code == 401
