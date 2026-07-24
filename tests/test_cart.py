"""Tests for the persistent, per-user cart."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_add_to_cart_and_persists_across_sessions(auth_client, product, user):
    resp = auth_client.post(
        reverse("v1:cart-items"),
        {"product_id": product.id, "quantity": 2},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["item_count"] == 2

    # A brand-new session for the same user must see the same cart.
    fresh = APIClient()
    fresh.force_authenticate(user=user)
    resp = fresh.get(reverse("v1:cart-detail"))
    assert resp.status_code == 200
    assert resp.data["item_count"] == 2
    assert resp.data["items"][0]["product"]["id"] == product.id
    assert resp.data["total_amount"] == "2000.00"


@pytest.mark.django_db
def test_cart_is_private_per_user(auth_client, product, django_user_model):
    auth_client.post(
        reverse("v1:cart-items"),
        {"product_id": product.id, "quantity": 1},
        format="json",
    )
    other = django_user_model.objects.create_user(email="other@example.com", password="pass12345")
    other_client = APIClient()
    other_client.force_authenticate(user=other)
    resp = other_client.get(reverse("v1:cart-detail"))
    assert resp.data["item_count"] == 0


@pytest.mark.django_db
def test_add_respects_stock(auth_client, product):
    resp = auth_client.post(
        reverse("v1:cart-items"),
        {"product_id": product.id, "quantity": product.stock + 1},
        format="json",
    )
    assert resp.status_code == 409
    assert resp.data["error"]["code"] == "insufficient_stock"


@pytest.mark.django_db
def test_update_quantity_zero_removes_line(auth_client, product):
    auth_client.post(
        reverse("v1:cart-items"),
        {"product_id": product.id, "quantity": 3},
        format="json",
    )
    resp = auth_client.patch(
        reverse("v1:cart-item-detail", args=[product.id]),
        {"quantity": 0},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["item_count"] == 0


@pytest.mark.django_db
def test_merge_guest_cart_on_login(auth_client, product):
    auth_client.post(
        reverse("v1:cart-items"),
        {"product_id": product.id, "quantity": 1},
        format="json",
    )
    resp = auth_client.post(
        reverse("v1:cart-merge"),
        {"items": [{"product_id": product.id, "quantity": 2}]},
        format="json",
    )
    assert resp.status_code == 200
    # 1 existing + 2 merged = 3 (within stock of 10)
    assert resp.data["item_count"] == 3


@pytest.mark.django_db
def test_checkout_creates_order_and_empties_cart(auth_client, product):
    auth_client.post(
        reverse("v1:cart-items"),
        {"product_id": product.id, "quantity": 2},
        format="json",
    )
    resp = auth_client.post(reverse("v1:cart-checkout"), {}, format="json")
    assert resp.status_code == 201
    assert resp.data["status"] == "pending"
    assert str(resp.data["total_amount"]) == "2000.00"

    # Cart is now empty.
    resp = auth_client.get(reverse("v1:cart-detail"))
    assert resp.data["item_count"] == 0
