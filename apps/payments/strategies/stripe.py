from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.conf import settings

from apps.core.exceptions import PaymentError

from ..models import PaymentStatus
from .base import PaymentResult, PaymentStrategy

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import guard
    import stripe
except ImportError:  # pragma: no cover
    stripe = None


_STRIPE_STATUS_MAP = {
    "succeeded": PaymentStatus.SUCCEEDED,
    "processing": PaymentStatus.PENDING,
    "requires_payment_method": PaymentStatus.PENDING,
    "requires_confirmation": PaymentStatus.PENDING,
    "requires_action": PaymentStatus.PENDING,
    "canceled": PaymentStatus.CANCELED,
}
def _to_plain_dict(obj) -> dict:
    #Converting a Stripe response object into a plain ``dict``
    
    if hasattr(obj, "to_dict_recursive"):
        return obj.to_dict_recursive()
    if hasattr(obj, "to_dict"):
        return dict(obj.to_dict())
    return dict(obj)

class StripeStrategy(PaymentStrategy):
    provider = "stripe"

    def _client(self):
        if stripe is None:
            raise PaymentError("The 'stripe' package is not installed.")
        if not settings.STRIPE_API_KEY:
            raise PaymentError("STRIPE_API_KEY is not configured.")
        stripe.api_key = settings.STRIPE_API_KEY
        return stripe

    def _fake_enabled(self) -> bool:
        """Simulate Stripe when explicitly enabled or when unconfigured.

        Lets the demo run end-to-end without a real Stripe key/SDK. Placeholder
        keys such as the sample "sk_test_xxx" also count as unconfigured.
        """
        key = settings.STRIPE_API_KEY or ""
        return (
            getattr(settings, "PAYMENTS_FAKE", False)
            or stripe is None
            or not key
            or key.endswith("xxx")
        )

    # ---- Frontend return URLs -------------------------------------------------
    def _success_url(self, payment) -> str:
        base = settings.STRIPE_SUCCESS_URL or settings.FRONTEND_BASE_URL
        return base + "?payment_id=" + str(payment.id) + "&status=success"

    def _cancel_url(self, payment) -> str:
        base = settings.STRIPE_CANCEL_URL or settings.FRONTEND_BASE_URL
        return base + "?payment_id=" + str(payment.id) + "&status=cancel"

    def _fake_initiate(self, payment) -> PaymentResult:
        """Simulate a hosted checkout by sending the browser straight to the
        success return URL, so the demo completes without real Stripe."""
        txn = "cs_sim_" + uuid.uuid4().hex[:24]
        url = self._success_url(payment) + "&simulated=1"
        logger.info("stripe SIMULATED session payment=%s session=%s", payment.id, txn)
        return PaymentResult(
            status=PaymentStatus.PENDING,
            transaction_id=txn,
            redirect_url=url,
            raw={"id": txn, "status": "open", "url": url, "simulated": True},
        )

    def _fake_succeeded(self, payment) -> PaymentResult:
        txn = payment.transaction_id or ("cs_sim_" + uuid.uuid4().hex[:24])
        return PaymentResult(
            status=PaymentStatus.SUCCEEDED,
            transaction_id=txn,
            raw={"id": txn, "status": "complete", "payment_status": "paid", "simulated": True},
        )

    @staticmethod
    def _to_minor_units(amount: Decimal) -> int:
        return int((amount * 100).to_integral_value())

    @staticmethod
    def _status_from_session(raw: dict) -> str:
        """Map a Stripe Checkout Session to our normalized PaymentStatus."""
        if raw.get("payment_status") == "paid":
            return PaymentStatus.SUCCEEDED
        if raw.get("status") == "expired":
            return PaymentStatus.CANCELED
        return PaymentStatus.PENDING

    def initiate(self, payment) -> PaymentResult:
        if self._fake_enabled():
            return self._fake_initiate(payment)
        try:
            client = self._client()
            session = client.checkout.Session.create(
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": settings.STRIPE_CURRENCY,
                            "product_data": {"name": "Payment #" + str(payment.id)},
                            "unit_amount": self._to_minor_units(payment.amount),
                        },
                        "quantity": 1,
                    }
                ],
                metadata={"payment_id": payment.id},
                success_url=self._success_url(payment),
                cancel_url=self._cancel_url(payment),
            )
            raw = _to_plain_dict(session)
            logger.info("stripe session created payment=%s session=%s", payment.id, raw.get("id"))
            return PaymentResult(
                status=self._status_from_session(raw),
                transaction_id=raw.get("id"),
                redirect_url=raw.get("url"),
                raw=raw,
            )
        except Exception as exc:
            logger.error("stripe initiate error payment=%s error=%s", payment.id, exc)
            message = getattr(exc, "user_message", None) or str(exc)
            raise PaymentError(message) from exc

    def confirm(self, payment, payload: dict) -> PaymentResult:
        """Stripe Checkout has no separate confirm step; re-read session status."""
        if self._fake_enabled():
            return self._fake_succeeded(payment)
        return self.verify(payment, payload)

    def verify(self, payment, payload: dict | None = None) -> PaymentResult:
        if self._fake_enabled():
            return self._fake_succeeded(payment)
        try:
            client = self._client()
            session = client.checkout.Session.retrieve(payment.transaction_id)
            raw = _to_plain_dict(session)
            return PaymentResult(
                status=self._status_from_session(raw),
                transaction_id=raw.get("id"),
                raw=raw,
            )
        except Exception as exc:
            logger.error("stripe verify error payment=%s error=%s", payment.id, exc)
            message = getattr(exc, "user_message", None) or str(exc)
            raise PaymentError(message) from exc

    def parse_webhook(self, request) -> dict:
        client = self._client()
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = client.Webhook.construct_event(
                payload=request.body,
                sig_header=sig_header,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except Exception as exc:  # invalid signature / payload
            raise PaymentError("Invalid Stripe webhook: " + str(exc)) from exc

        obj = _to_plain_dict(event["data"]["object"])
        event_type = event["type"]
        status = PaymentStatus.PENDING
        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            status = PaymentStatus.SUCCEEDED
        elif event_type == "checkout.session.expired":
            status = PaymentStatus.CANCELED
        elif event_type == "checkout.session.async_payment_failed":
            status = PaymentStatus.FAILED

        return {
            "transaction_id": obj.get("id"),
            "status": status,
            "event_type": event_type,
            "raw": _to_plain_dict(event),
        }