"""Provider-facing webhook endpoints.

These are unauthenticated (providers can't send JWTs) but each strategy
validates the provider signature before anything is trusted.
"""
import logging

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import PaymentError

from ..models import PaymentProvider
from ..service import handle_webhook

logger = logging.getLogger(__name__)


def _dispatch(provider, request):
    try:
        payment = handle_webhook(provider, request)
    except PaymentError as exc:
        logger.warning("webhook rejected provider=%s error=%s", provider, exc)
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    logger.info("webhook accepted provider=%s payment=%s", provider, getattr(payment, "id", None))
    return Response({"received": True}, status=status.HTTP_200_OK)


class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Webhooks"],
        summary="Stripe provider webhook (signature verified)",
        request=serializers.DictField(),
        responses={200: inline_serializer("WebhookResponse", {"received": serializers.BooleanField()})},
    )
    def post(self, request):
        return _dispatch(PaymentProvider.STRIPE, request)


class BkashWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Webhooks"],
        summary="bKash provider webhook (signature verified)",
        request=serializers.DictField(),
        responses={200: inline_serializer("BkashWebhookResponse", {"received": serializers.BooleanField()})},
    )
    def post(self, request):
        return _dispatch(PaymentProvider.BKASH, request)