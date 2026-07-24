from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order

from .models import Payment, PaymentProvider
from .serializers import (
    ConfirmPaymentSerializer,
    InitiatePaymentSerializer,
    PaymentSerializer,
)
from .service import PaymentService
from .strategies import get_strategy


def _owned_payments(user):
    """Payments belonging to the requesting user's own orders."""
    return Payment.objects.filter(order__user=user).select_related("order")

class PaymentConfigView(APIView):
    """Public payment configuration for the browser (e.g. Stripe publishable key).

    The frontend calls this before checkout to decide whether to mount a real
    Stripe.js card field or fall back to the simulated flow.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        stripe_strategy = get_strategy(PaymentProvider.STRIPE)
        return Response(
            {
                "stripe": {
                    "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
                    "currency": settings.STRIPE_CURRENCY,
                    # True => no real key configured; browser should skip Stripe.js
                    # and let the backend simulate the charge instead.
                    "simulated": stripe_strategy._fake_enabled(),
                }
            }
        )
class PaymentListView(APIView):
    """List the current user's payments."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = _owned_payments(request.user)
        return Response(PaymentSerializer(payments, many=True).data)


class PaymentDetailView(APIView):
    """Retrieve a single payment owned by the user."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payment = get_object_or_404(_owned_payments(request.user), pk=pk)
        return Response(PaymentSerializer(payment).data)


class PaymentInitiateView(APIView):
    """Initiate a payment for one of the user's pending orders."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = get_object_or_404(
            Order, pk=serializer.validated_data["order_id"], user=request.user
        )
        service = PaymentService(serializer.validated_data["provider"])
        payment = service.initiate(order)
        data = PaymentSerializer(payment).data
        # Surface the client action (redirect/secret) from the raw response.
        data["client_secret"] = payment.raw_response.get("client_secret")
        data["redirect_url"] = payment.raw_response.get("redirect_url")
        return Response(data, status=status.HTTP_201_CREATED)


class PaymentConfirmView(APIView):
    """Confirm/execute a payment (polling flow or client callback)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConfirmPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = get_object_or_404(
            _owned_payments(request.user),
            pk=serializer.validated_data["payment_id"],
        )
        service = PaymentService(payment.provider)
        payment = service.confirm(payment, serializer.validated_data["payload"])
        return Response(PaymentSerializer(payment).data)


class PaymentVerifyView(APIView):
    """Query the provider for the payment's current status."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payment = get_object_or_404(_owned_payments(request.user), pk=pk)
        service = PaymentService(payment.provider)
        payment = service.verify(payment)
        return Response(PaymentSerializer(payment).data)