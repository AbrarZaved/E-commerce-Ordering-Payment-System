from rest_framework import serializers

from apps.products.serializers import ProductSerializer

from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "product", "quantity", "subtotal")
        read_only_fields = fields


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "total_amount", "item_count", "updated_at")
        read_only_fields = fields

    def get_total_amount(self, obj):
        return str(obj.total_amount())

    def get_item_count(self, obj):
        return obj.item_count()


class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    # 0 removes the line item.
    quantity = serializers.IntegerField(min_value=0)


class MergeCartSerializer(serializers.Serializer):
    items = AddCartItemSerializer(many=True)
