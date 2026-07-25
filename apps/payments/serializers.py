from rest_framework import serializers

from .models import Payment
from .strategies import supported_providers


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "order",
            "provider",
            "transaction_id",
            "status",
            "amount",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=supported_providers())


class ConfirmPaymentSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(min_value=1)
    # Free-form provider payload (e.g. Stripe payment_method); validated by strategy.
    payload = serializers.DictField(required=False, default=dict)


class AdminPaymentSerializer(serializers.ModelSerializer):
    """Every payment + the customer's details, for the admin panel."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    order_id = serializers.IntegerField(source="order.id", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "user_id",
            "user_email",
            "user_full_name",
            "order_id",
            "order_status",
            "provider",
            "transaction_id",
            "status",
            "amount",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ResumePaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    # Optional: override the provider; defaults to the order's last attempt.
    provider = serializers.ChoiceField(choices=supported_providers(), required=False)