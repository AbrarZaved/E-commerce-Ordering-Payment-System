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
            user=order.user,
            provider=self.provider,
            amount=order.total_amount,
            status=PaymentStatus.INITIATED,
        )
        return self._run_strategy_initiate(payment)

    @transaction.atomic
    def initiate_from_cart(self, user) -> Payment:
        """Initiate a payment straight from the user's cart WITHOUT creating an
        order first.

        The order is recorded only if/when the payment succeeds (see
        ``_apply_result``), so a failed or abandoned checkout never leaves a
        pending order behind.
        """
        from apps.cart.services import snapshot_cart

        snapshot, amount = snapshot_cart(user)
        payment = Payment.objects.create(
            user=user,
            provider=self.provider,
            amount=amount,
            items_snapshot=snapshot,
            status=PaymentStatus.INITIATED,
        )
        return self._run_strategy_initiate(payment)

    def _run_strategy_initiate(self, payment: Payment) -> Payment:
        result = self.strategy.initiate(payment)
        payment.transaction_id = result.transaction_id
        payment.status = result.status
        # Persist the provider payload plus normalized client-action fields so the
        # API layer can surface a redirect URL / client secret with no provider
        # branching (works for Stripe Checkout, bKash, and any future provider).
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
    def abandon(self, payment: Payment, *, failed: bool = False) -> Payment:
        # Finalize a payment the customer did NOT complete.

  
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == PaymentStatus.SUCCEEDED:
            return payment
        payment.status = PaymentStatus.FAILED if failed else PaymentStatus.CANCELED
        payment.save(update_fields=["status", "updated_at"])
        logger.info("payment %s finalized as %s (not completed)", payment.id, payment.status)
        return payment

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
            from apps.cart.services import clear_cart

            if payment.order_id is None:
                # Deferred storefront flow: create the order ONLY now that the
                # payment has succeeded, so no pending order is ever recorded for
                # a failed or abandoned checkout.
                from apps.orders.services import create_paid_order

                order = create_paid_order(payment.user, payment.items_snapshot)
                payment.order = order
                payment.save(update_fields=["order", "updated_at"])
                clear_cart(payment.user)
                logger.info("order %s created + paid via deferred payment %s", order.id, payment.id)
            else:
                # Order-based flow (a pending order was pre-created): mark it paid.
                order = Order.objects.select_for_update().get(pk=payment.order_id)
                if order.status != OrderStatus.PAID:
                    reduce_stock_for_order(order)
                    order.mark_paid()
                    # Empty the cart only now that payment has succeeded, so a
                    # failed/cancelled/abandoned payment leaves the cart for a retry.
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
