"""Webhook parsing/handling tests with simulated provider payloads."""
import json

import pytest

from apps.orders.models import OrderStatus
from apps.orders.services import create_order
from apps.payments.models import Payment, PaymentProvider, PaymentStatus


class FakeRequest:
    def __init__(self, body, meta=None):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.META = meta or {}


@pytest.mark.django_db
def test_bkash_webhook_marks_paid(user, product, settings):
    settings.BKASH_WEBHOOK_SECRET = ""  # skip signature check in test
    order = create_order(user, [{"product_id": product.id, "quantity": 2}])
    payment = Payment.objects.create(
        order=order, provider=PaymentProvider.BKASH, amount=order.total_amount,
        transaction_id="TR0011abc", status=PaymentStatus.PENDING,
    )

    from apps.payments.service import handle_webhook
    req = FakeRequest({"paymentID": "TR0011abc", "transactionStatus": "Completed"})
    result = handle_webhook(PaymentProvider.BKASH, req)

    assert result.status == PaymentStatus.SUCCEEDED
    order.refresh_from_db()
    assert order.status == OrderStatus.PAID
    product.refresh_from_db()
    assert product.stock == 8


@pytest.mark.django_db
def test_bkash_webhook_failed_keeps_order_pending(user, product, settings):
    settings.BKASH_WEBHOOK_SECRET = ""
    order = create_order(user, [{"product_id": product.id, "quantity": 1}])
    Payment.objects.create(
        order=order, provider=PaymentProvider.BKASH, amount=order.total_amount,
        transaction_id="TR0011fail", status=PaymentStatus.PENDING,
    )

    from apps.payments.service import handle_webhook
    req = FakeRequest({"paymentID": "TR0011fail", "transactionStatus": "Failed"})
    result = handle_webhook(PaymentProvider.BKASH, req)

    assert result.status == PaymentStatus.FAILED
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING


@pytest.mark.django_db
def test_webhook_unknown_transaction_returns_none(settings):
    settings.BKASH_WEBHOOK_SECRET = ""
    from apps.payments.service import handle_webhook
    req = FakeRequest({"paymentID": "does-not-exist", "transactionStatus": "Completed"})
    assert handle_webhook(PaymentProvider.BKASH, req) is None
