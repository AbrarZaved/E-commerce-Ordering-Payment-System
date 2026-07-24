"""Tests proving the Strategy pattern is extensible without branching."""
import pytest

from apps.core.exceptions import PaymentError
from apps.payments.strategies import get_strategy, supported_providers
from apps.payments.strategies.base import PaymentStrategy


def test_registry_returns_correct_strategy():
    assert get_strategy("stripe").provider == "stripe"
    assert get_strategy("bkash").provider == "bkash"


def test_unknown_provider_raises():
    with pytest.raises(PaymentError):
        get_strategy("paypal")


def test_supported_providers_listed():
    assert set(supported_providers()) == {"stripe", "bkash"}


def test_can_register_third_provider_without_touching_service():
    """Demonstrates extensibility: a new provider only needs a class + registry entry."""
    from apps.payments import strategies as strat_module
    from apps.payments.strategies.base import PaymentResult

    class PaypalStrategy(PaymentStrategy):
        provider = "paypal"

        def initiate(self, payment):
            return PaymentResult(status="pending", transaction_id="pp_1")

        def confirm(self, payment, payload):
            return PaymentResult(status="succeeded", transaction_id="pp_1")

        def verify(self, payment, payload=None):
            return PaymentResult(status="succeeded", transaction_id="pp_1")

        def parse_webhook(self, request):
            return {"transaction_id": "pp_1", "status": "succeeded"}

    strat_module._REGISTRY["paypal"] = PaypalStrategy
    try:
        assert get_strategy("paypal").provider == "paypal"
    finally:
        strat_module._REGISTRY.pop("paypal", None)
