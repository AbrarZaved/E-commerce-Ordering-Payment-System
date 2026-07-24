"""End-to-end-ish API tests for order creation + checkout."""
import pytest
from django.urls import reverse

from apps.orders.models import OrderStatus
from apps.payments.models import PaymentStatus


@pytest.mark.django_db
def test_create_order_via_api(auth_client, product):
    resp = auth_client.post(
        reverse("v1:order-list"),
        {"items": [{"product_id": product.id, "quantity": 2}]},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["status"] == OrderStatus.PENDING
    assert str(resp.data["total_amount"]) == "2000.00"


@pytest.mark.django_db
def test_user_only_sees_own_orders(auth_client, product, django_user_model):
    other = django_user_model.objects.create_user(email="other@example.com", password="pass12345")
    from apps.orders.services import create_order
    create_order(other, [{"product_id": product.id, "quantity": 1}])

    resp = auth_client.get(reverse("v1:order-list"))
    assert resp.status_code == 200
    assert resp.data["count"] == 0


@pytest.mark.django_db
def test_payment_success_marks_order_paid_and_reduces_stock(user, product, monkeypatch):
    """Drive the PaymentService with a fake strategy result (no network)."""
    from apps.orders.services import create_order
    from apps.payments import service as service_module
    from apps.payments.service import PaymentService
    from apps.payments.strategies.base import PaymentResult

    order = create_order(user, [{"product_id": product.id, "quantity": 3}])

    svc = PaymentService("stripe")
    monkeypatch.setattr(
        svc.strategy, "initiate",
        lambda payment: PaymentResult(status=PaymentStatus.PENDING, transaction_id="pi_test_1"),
    )
    payment = svc.initiate(order)
    assert payment.transaction_id == "pi_test_1"

    monkeypatch.setattr(
        svc.strategy, "confirm",
        lambda payment, payload: PaymentResult(status=PaymentStatus.SUCCEEDED, transaction_id="pi_test_1"),
    )
    payment = svc.confirm(payment, {})

    order.refresh_from_db()
    product.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert order.status == OrderStatus.PAID
    assert product.stock == 7
