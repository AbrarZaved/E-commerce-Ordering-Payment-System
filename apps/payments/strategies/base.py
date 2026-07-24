"""Abstract payment strategy contract."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaymentResult:
    """Normalized result returned by every strategy method.

    Keeps provider-specific payloads in ``raw`` while exposing a consistent
    surface (status/transaction_id) to the orchestration layer.
    """

    status: str
    transaction_id: str | None = None
    # A URL/token the client uses to complete payment (e.g. Stripe client_secret,
    # bKash bkashURL).
    redirect_url: str | None = None
    client_secret: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentStrategy(abc.ABC):
    """Interface every payment provider must implement.

    The orchestration layer (``PaymentService``) only ever talks to this
    interface, so providers are fully interchangeable.
    """

    provider: str = ""

    @abc.abstractmethod
    def initiate(self, payment) -> PaymentResult:
        """Create the payment intent/session with the provider."""

    @abc.abstractmethod
    def confirm(self, payment, payload: dict) -> PaymentResult:
        """Confirm/execute the payment (client callback or explicit execute)."""

    @abc.abstractmethod
    def verify(self, payment, payload: dict | None = None) -> PaymentResult:
        """Verify the payment's current status directly with the provider."""

    @abc.abstractmethod
    def parse_webhook(self, request) -> dict:
        """Validate signature and normalize an inbound webhook request.

        Must return a dict containing at least ``transaction_id`` and ``status``.
        """
