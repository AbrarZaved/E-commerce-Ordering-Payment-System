"""Payment strategy registry.

Adding a third provider is intentionally a one-line change here plus a new
strategy class -- no branching in order/payment orchestration logic. This is the
core design constraint of the assessment.
"""
from apps.core.exceptions import PaymentError

from ..models import PaymentProvider
from .base import PaymentResult, PaymentStrategy
from .bkash import BkashStrategy
from .stripe import StripeStrategy

_REGISTRY: dict[str, type[PaymentStrategy]] = {
    PaymentProvider.STRIPE: StripeStrategy,
    PaymentProvider.BKASH: BkashStrategy,
}


def get_strategy(provider: str) -> PaymentStrategy:
    try:
        strategy_cls = _REGISTRY[provider]
    except KeyError as exc:
        raise PaymentError(f"Unsupported payment provider: {provider}") from exc
    return strategy_cls()


def supported_providers() -> list[str]:
    return list(_REGISTRY.keys())


__all__ = [
    "PaymentStrategy",
    "PaymentResult",
    "StripeStrategy",
    "BkashStrategy",
    "get_strategy",
    "supported_providers",
]
