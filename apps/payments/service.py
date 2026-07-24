"""Payment orchestration.

``PaymentService`` selects a strategy at runtime based on ``provider`` and
contains ZERO provider-specific branching. Adding a provider requires only a new
strategy class + registry entry (see ``strategies/__init__.py``).
"""
from __future__ import annotations

import logging

from django.db import transaction

from apps.core.exceptions import InvalidOrderState, PaymentError
from apps.orders.models import Order, OrderStatus
from apps.orders.services import reduce_stock_for_order
from apps.cart.services import clear_cart
from .models import Payment, PaymentStatus
from .strategies import get_strategy

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, provider: str):
        self.provider = provider
        self.strategy = get_strategy(provider)

    @transaction.atomic
    def initiate(self, order: Order) -> Payment:
        if order.status != OrderStatus.PENDING:
            raise InvalidOrderState("Only pending orders can be paid.")

        payment = Payment.objects.create(
            order=order,
            provider=self.provider,
            amount=order.total_amount,
            status=PaymentStatus.INITIATED,
        )
        result = self.strategy.initiate(payment)
        payment.transaction_id = result.transaction_id
        payment.status = result.status
        raw = dict(result.raw or {})
        if result.redirect_url:
            raw["redirect_url"] = result.redirect_url
        if result.client_secret:
            raw["client_secret"] = result.client_secret
        payment.raw_response = raw
        payment.save(update_fields=["transaction_id", "status", "raw_response", "updated_at"])
        logger.info("payment initiated id=%s provider=%s status=%s", payment.id, self.provider, payment.status)
        return payment

    @transaction.atomic
    def confirm(self, payment: Payment, payload: dict) -> Payment:
        result = self.strategy.confirm(payment, payload)
        return self._apply_result(payment, result.status, result.raw, result.transaction_id)

    @transaction.atomic
    def verify(self, payment: Payment, payload: dict | None = None) -> Payment:
        result = self.strategy.verify(payment, payload)
        return self._apply_result(payment, result.status, result.raw, result.transaction_id)

    @transaction.atomic
    def _apply_result(self, payment: Payment, status: str, raw: dict, transaction_id=None) -> Payment:
        """Apply a normalized strategy result and drive the order state machine."""
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        already_succeeded = payment.status == PaymentStatus.SUCCEEDED

        payment.status = status
        if transaction_id:
            payment.transaction_id = transaction_id
        if raw:
            payment.raw_response = raw
        payment.save(update_fields=["status", "transaction_id", "raw_response", "updated_at"])

        # Idempotency: only transition the order + reduce stock once.
        if status == PaymentStatus.SUCCEEDED and not already_succeeded:
            order = Order.objects.select_for_update().get(pk=payment.order_id)
            if order.status != OrderStatus.PAID:
                reduce_stock_for_order(order)
                order.mark_paid()
                clear_cart(order.user)
                logger.info("order %s marked paid via payment %s", order.id, payment.id)
        elif status == PaymentStatus.FAILED:
            logger.warning("payment %s failed", payment.id)

        return payment


def handle_webhook(provider: str, request) -> Payment | None:
    """Entry point for provider webhooks. Provider-agnostic."""
    service = PaymentService(provider)
    parsed = service.strategy.parse_webhook(request)
    transaction_id = parsed.get("transaction_id")
    if not transaction_id:
        raise PaymentError("Webhook missing transaction id.")

    try:
        payment = Payment.objects.get(transaction_id=transaction_id, provider=provider)
    except Payment.DoesNotExist:
        logger.warning("webhook for unknown transaction %s (%s)", transaction_id, provider)
        return None

    return service._apply_result(payment, parsed["status"], parsed.get("raw", {}), transaction_id)
