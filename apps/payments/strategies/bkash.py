from __future__ import annotations

import logging
import uuid

from django.conf import settings

from apps.core.exceptions import PaymentError

from ..models import PaymentStatus
from .base import PaymentResult, PaymentStrategy

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import guard
    import requests
except ImportError:  # pragma: no cover
    requests = None


_BKASH_STATUS_MAP = {
    "Completed": PaymentStatus.SUCCEEDED,
    "Authorized": PaymentStatus.PENDING,
    "Initiated": PaymentStatus.PENDING,
    "Pending": PaymentStatus.PENDING,
    "Cancelled": PaymentStatus.CANCELED,
    "Failed": PaymentStatus.FAILED,
}


class BkashStrategy(PaymentStrategy):
    provider = "bkash"

    def _require(self):
        if requests is None:
            raise PaymentError("The 'requests' package is not installed.")
        missing = [
            key
            for key in ("BKASH_APP_KEY", "BKASH_APP_SECRET", "BKASH_USERNAME", "BKASH_PASSWORD")
            if not getattr(settings, key)
        ]
        if missing:
            raise PaymentError(f"Missing bKash configuration: {', '.join(missing)}")

    def _fake_enabled(self) -> bool:
        #Simulating bKash when explicitly enabled or when unconfigured.

  
        missing = [
            key
            for key in ("BKASH_APP_KEY", "BKASH_APP_SECRET", "BKASH_USERNAME", "BKASH_PASSWORD")
            if not getattr(settings, key) or str(getattr(settings, key)).startswith("your_")
        ]
        return getattr(settings, "PAYMENTS_FAKE", False) or requests is None or bool(missing)

    def _fake_initiate(self, payment) -> PaymentResult:
        txn = f"TR{uuid.uuid4().hex[:10].upper()}"
        url = "https://sandbox.bkash.local/checkout/" + txn
        logger.info("bkash SIMULATED payment created payment=%s bkash_id=%s", payment.id, txn)
        return PaymentResult(
            status=PaymentStatus.PENDING,
            transaction_id=txn,
            redirect_url=url,
            raw={"paymentID": txn, "transactionStatus": "Initiated", "bkashURL": url, "simulated": True},
        )

    def _fake_succeeded(self, payment) -> PaymentResult:
        txn = payment.transaction_id or f"TR{uuid.uuid4().hex[:10].upper()}"
        return PaymentResult(
            status=PaymentStatus.SUCCEEDED,
            transaction_id=txn,
            raw={"paymentID": txn, "transactionStatus": "Completed", "simulated": True},
        )

    def _grant_token(self) -> str:
        self._require()
        resp = requests.post(
            f"{settings.BKASH_BASE_URL}/tokenized/checkout/token/grant",
            json={
                "app_key": settings.BKASH_APP_KEY,
                "app_secret": settings.BKASH_APP_SECRET,
            },
            headers={
                "username": settings.BKASH_USERNAME,
                "password": settings.BKASH_PASSWORD,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        data = resp.json()
        token = data.get("id_token")
        if not token:
            raise PaymentError(f"bKash token grant failed: {data}")
        return token

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": token,
            "X-APP-Key": settings.BKASH_APP_KEY,
            "Content-Type": "application/json",
        }
    def _callback_url(self, payment) -> str:
        #Frontend URL bKash redirects back to after the customer authorizes"

        base = getattr(settings, "BKASH_CALLBACK_URL", "") or settings.FRONTEND_BASE_URL
        return base + "?payment_id=" + str(payment.id) + "&provider=bkash"
    
    def initiate(self, payment) -> PaymentResult:
        if self._fake_enabled():
            return self._fake_initiate(payment)
        token = self._grant_token()
        resp = requests.post(
            f"{settings.BKASH_BASE_URL}/tokenized/checkout/create",
            json={
                "mode": "0011",
                "payerReference": str(payment.id),
                "callbackURL": self._callback_url(payment),
                "amount": str(payment.amount),
                "currency": "BDT",
                "intent": "sale",
                "merchantInvoiceNumber": f"PAY-{payment.id}",
            },
            headers=self._headers(token),
            timeout=30,
        )
        data = resp.json()
        payment_id = data.get("paymentID")
        if not payment_id:
            raise PaymentError(f"bKash create payment failed: {data}")
        logger.info("bkash payment created payment=%s bkash_id=%s", payment.id, payment_id)
        return PaymentResult(
            status=_BKASH_STATUS_MAP.get(data.get("transactionStatus"), PaymentStatus.PENDING),
            transaction_id=payment_id,
            redirect_url=data.get("bkashURL"),
            raw=data,
        )

    def confirm(self, payment, payload: dict) -> PaymentResult:
        """Execute the payment after the customer authorizes it."""
        if self._fake_enabled():
            return self._fake_succeeded(payment)
        token = self._grant_token()
        resp = requests.post(
            f"{settings.BKASH_BASE_URL}/tokenized/checkout/execute",
            json={"paymentID": payment.transaction_id},
            headers=self._headers(token),
            timeout=30,
        )
        data = resp.json()
        return PaymentResult(
            status=_BKASH_STATUS_MAP.get(data.get("transactionStatus"), PaymentStatus.PENDING),
            transaction_id=data.get("paymentID", payment.transaction_id),
            raw=data,
        )

    def verify(self, payment, payload: dict | None = None) -> PaymentResult:
        if self._fake_enabled():
            return self._fake_succeeded(payment)
        token = self._grant_token()
        resp = requests.post(
            f"{settings.BKASH_BASE_URL}/tokenized/checkout/payment/status",
            json={"paymentID": payment.transaction_id},
            headers=self._headers(token),
            timeout=30,
        )
        data = resp.json()
        return PaymentResult(
            status=_BKASH_STATUS_MAP.get(data.get("transactionStatus"), PaymentStatus.PENDING),
            transaction_id=payment.transaction_id,
            raw=data,
        )

    def parse_webhook(self, request) -> dict:
        import hmac
        import json
        from hashlib import sha256

        secret = settings.BKASH_WEBHOOK_SECRET
        if secret:
            signature = request.META.get("HTTP_X_BKASH_SIGNATURE", "")
            expected = hmac.new(secret.encode(), request.body, sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise PaymentError("Invalid bKash webhook signature.")

        try:
            data = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            raise PaymentError(f"Invalid bKash webhook payload: {exc}") from exc

        return {
            "transaction_id": data.get("paymentID"),
            "status": _BKASH_STATUS_MAP.get(data.get("transactionStatus"), PaymentStatus.PENDING),
            "event_type": data.get("transactionStatus", "unknown"),
            "raw": data,
        }