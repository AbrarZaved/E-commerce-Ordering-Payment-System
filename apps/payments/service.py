"""Payment orchestration.

``PaymentService`` selects a strategy at runtime based on ``provider`` and
contains ZERO provider-specific branching. Adding a provider requires only a new
strategy class + registry entry.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import InvalidOrderState, PaymentError
from apps.orders.models import Order, OrderStatus
from apps.orders.services import create_order, create_paid_order, reduce_stock_for_order
from apps.cart.services import snapshot_cart
from .models import Payment, PaymentStatus
from .strategies import get_strategy

logger = logging.getLogger(__name__)

# Terminal payment states that must never be transitioned again.
_FINAL_STATUSES = (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED, PaymentStatus.CANCELED)


def pending_timeout() -> timedelta:
    """How long a payment may stay pending before auto-failing."""
    minutes = getattr(settings, "PAYMENT_PENDING_TIMEOUT_MINUTES", 30)
    return timedelta(minutes=minutes)


class PaymentService:
    def __init__(self, provider: str):
        self.provider = provider
        self.strategy = get_strategy(provider)

    @transaction.atomic
    def initiate(self, order: Order) -> Payment:
        """Initiate payment for an existing pending order."""
        if order.status != OrderStatus.PENDING:
            raise InvalidOrderState("Only pending orders can be paid.")

        payment = Payment.objects.create(
            order=order,
            user=order.user,
            provider=self.provider,
            amount=order.total_amount,
            status=PaymentStatus.INITIATED,
            expires_at=timezone.now() + pending_timeout(),
        )
        return self._run_strategy_initiate(payment)
    
    @transaction.atomic
    def resume(self, order: Order) -> Payment:
        # Re-open checkout for a pending order by starting a fresh attempt.

        if order.status != OrderStatus.PENDING:
            raise InvalidOrderState("Only pending orders can be resumed.")
        order.payments.filter(
            status__in=[PaymentStatus.INITIATED, PaymentStatus.PENDING]
        ).update(status=PaymentStatus.CANCELED)
        return self.initiate(order)

    @transaction.atomic
    def initiate_from_cart(self, user) -> Payment:
        """Create a PENDING order from the user's cart up front, then initiate
        payment.

        Creating the order immediately means ``order_id`` is persisted for
        pending and cancelled payments too. Stock is still only reduced when the
        payment succeeds.
        """

    # Cancel any lingering pending checkout for this user before starting a
    # fresh one (the cart still holds the items, so the old order is stale).
        self._supersede_open_checkouts(user)

        snapshot, _amount = snapshot_cart(user)
        order = create_order(user, snapshot)  # status=pending, no stock change

        payment = Payment.objects.create(
            order=order,    
            user=user,
            provider=self.provider,
            amount=order.total_amount,
            items_snapshot=snapshot,
            status=PaymentStatus.INITIATED,
            expires_at=timezone.now() + pending_timeout(),
        )
        return self._run_strategy_initiate(payment)
    def _supersede_open_checkouts(self, user, keep_order_id=None):
        # Cancel a user's other lingering PENDING orders + their open payments.
        stale_orders = Order.objects.select_for_update().filter(
            user=user, status=OrderStatus.PENDING
        )
        if keep_order_id is not None:
            stale_orders = stale_orders.exclude(pk=keep_order_id)
        for order in stale_orders:
            # Cancel still-open payments first so a lost countdown/webhook can't
            # later flip the now-cancelled order.
            Payment.objects.filter(
                order=order,
                status__in=[PaymentStatus.INITIATED, PaymentStatus.PENDING],
            ).update(status=PaymentStatus.CANCELED)
            order.mark_canceled()
            logger.info(
                "superseded stale pending order %s for user %s", order.id, user.id
            )               

    def _run_strategy_initiate(self, payment: Payment) -> Payment:
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

        # Schedule an automatic expiry once the surrounding transaction commits.
        payment_id = payment.id
        countdown = max(int(pending_timeout().total_seconds()), 0)

        def _schedule_expiry():
            from .tasks import expire_pending_payment

            # In eager mode (local dev) apply_async runs immediately and ignores
            # countdown, which would fail the payment instantly -- skip it there
            # and rely on the periodic beat sweep instead.
            if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                return
            expire_pending_payment.apply_async(args=[payment_id], countdown=countdown)

        transaction.on_commit(_schedule_expiry)

        logger.info(
            "payment initiated id=%s provider=%s status=%s order=%s",
            payment.id, self.provider, payment.status, payment.order_id,
        )
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
        """Finalize a payment the customer did NOT complete."""
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == PaymentStatus.SUCCEEDED:
            return payment
        new_status = PaymentStatus.FAILED if failed else PaymentStatus.CANCELED
        return self._apply_result(payment, new_status, payment.raw_response or {})

    @transaction.atomic
    def expire(self, payment: Payment) -> Payment:
        """Fail a still-pending payment that has exceeded its timeout."""
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status in _FINAL_STATUSES:
            return payment
        raw = dict(payment.raw_response or {})
        raw["expired_reason"] = "pending_timeout"
        return self._apply_result(payment, PaymentStatus.FAILED, raw)

    @transaction.atomic
    def _apply_result(self, payment: Payment, status: str, raw: dict, transaction_id=None) -> Payment:
        """Apply a normalized strategy result and drive the order state machine."""
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        already_succeeded = payment.status == PaymentStatus.SUCCEEDED
        already_final = payment.status in _FINAL_STATUSES

        payment.status = status
        if transaction_id:
            payment.transaction_id = transaction_id
        if raw:
            payment.raw_response = raw
        payment.save(update_fields=["status", "transaction_id", "raw_response", "updated_at"])

        if status == PaymentStatus.SUCCEEDED and not already_succeeded:
            from apps.cart.services import clear_cart

            if payment.order_id is None:
                # Fallback for the legacy deferred flow (no pre-created order).
                order = create_paid_order(payment.user, payment.items_snapshot)
                payment.order = order
                payment.save(update_fields=["order", "updated_at"])
            else:
                order = Order.objects.select_for_update().get(pk=payment.order_id)
                if order.status != OrderStatus.PAID:
                    reduce_stock_for_order(order)
                    order.mark_paid()
            user = payment.user or (payment.order.user if payment.order_id else None)
            if user:
                clear_cart(user)
            logger.info("order %s marked paid via payment %s", payment.order_id, payment.id)

        elif status in (PaymentStatus.FAILED, PaymentStatus.CANCELED) and not already_final:
            logger.warning(
                "payment %s -> %s for order %s", payment.id, status, payment.order_id
            )

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