from rest_framework import serializers

from apps.products.serializers import ProductSerializer

from .models import Order, OrderItem


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "quantity", "price", "subtotal")
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ("id", "user", "full_name", "status", "total_amount", "items", "created_at", "updated_at")
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.user.full_name}"


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("An order must contain at least one item.")
        seen = set()
        for item in value:
            if item["product_id"] in seen:
                raise serializers.ValidationError("Duplicate product in order; combine quantities.")
            seen.add(item["product_id"])
        return value
