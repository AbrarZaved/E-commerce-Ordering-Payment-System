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
    order_id = serializers.IntegerField(min_value=1)
    provider = serializers.ChoiceField(choices=supported_providers())


class ConfirmPaymentSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(min_value=1)
    # Free-form provider payload (e.g. Stripe payment_method); validated by strategy.
    payload = serializers.DictField(required=False, default=dict)
