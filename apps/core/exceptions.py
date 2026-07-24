"""Custom exceptions and a consistent error response format."""
import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ServiceError(APIException):
    """Base class for domain/service level errors."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A service error occurred."
    default_code = "service_error"


class InsufficientStockError(ServiceError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Insufficient stock for the requested quantity."
    default_code = "insufficient_stock"


class PaymentError(ServiceError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "The payment could not be processed."
    default_code = "payment_error"


class InvalidOrderState(ServiceError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The order is not in a valid state for this action."
    default_code = "invalid_order_state"


def api_exception_handler(exc, context):
    """Wrap DRF's default handler to produce a consistent error envelope.

    Response shape::

        {"error": {"code": "...", "message": "...", "details": {...}}}
    """
    response = exception_handler(exc, context)
    if response is None:
        return response

    code = getattr(exc, "default_code", "error")
    detail = response.data
    message = detail.get("detail") if isinstance(detail, dict) else detail
    if message is None:
        message = "An error occurred."

    response.data = {
        "error": {
            "code": code,
            "message": message if isinstance(message, str) else "Validation failed.",
            "details": detail,
        }
    }
    return response
