from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import DefaultPagination
from apps.orders.models import Order, OrderStatus

from .models import Payment, PaymentProvider, PaymentStatus
from .serializers import (
    AdminPaymentSerializer,
    ConfirmPaymentSerializer,
    InitiatePaymentSerializer,
    PaymentSerializer,
    ResumePaymentSerializer,
)
from .service import PaymentService
from .strategies import get_strategy


def _owned_payments(user):
    """Payments belonging to the requesting user's own orders."""
    return Payment.objects.filter(Q(user=user) | Q(order__user=user)).select_related("order")

class PaymentConfigView(APIView):
    # Public payment configuration for the browser (e.g. Stripe publishable key).



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
        service = PaymentService(serializer.validated_data["provider"])
        payment = service.initiate_from_cart(request.user)
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


class PaymentCancelView(APIView):
    # Finalize a payment the customer did not complete.



    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payment = get_object_or_404(_owned_payments(request.user), pk=pk)
        raw = request.data.get("failed", request.query_params.get("failed", False))
        failed = str(raw).lower() in ("1", "true", "yes")
        service = PaymentService(payment.provider)
        payment = service.abandon(payment, failed=failed)
        return Response(PaymentSerializer(payment).data)


class PaymentResumeView(APIView):
    """Resume checkout for one of the user's pending orders."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ResumePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = get_object_or_404(
            Order.objects.filter(user=request.user),
            pk=serializer.validated_data["order_id"],
        )
        if order.status != OrderStatus.PENDING:
            return Response(
                {"error": {"message": "Only pending orders can be resumed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        provider = serializer.validated_data.get("provider")
        if not provider:
            last_payment = order.payments.order_by("-created_at").first()
            provider = last_payment.provider if last_payment else PaymentProvider.STRIPE
        service = PaymentService(provider)
        payment = service.resume(order)
        data = PaymentSerializer(payment).data
        data["client_secret"] = payment.raw_response.get("client_secret")
        data["redirect_url"] = payment.raw_response.get("redirect_url")
        return Response(data, status=status.HTTP_201_CREATED)


class AdminPaymentListView(APIView):
    """Staff-only: list every payment (paid, pending, failed, canceled) with
    the customer's details for the admin panel."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        payments = Payment.objects.select_related("user", "order").all()
        status_param = request.query_params.get("status")
        if status_param:
            payments = payments.filter(status=status_param)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(payments, request, view=self)
        return paginator.get_paginated_response(
            AdminPaymentSerializer(page, many=True).data
        )