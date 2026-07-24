from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent")


class CategoryTreeSerializer(serializers.Serializer):
    """Read-only serializer describing the nested tree payload shape."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    children = serializers.ListField(child=serializers.DictField())


class ProductSerializer(serializers.ModelSerializer):
    is_available = serializers.BooleanField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "sku",
            "description",
            "price",
            "stock",
            "status",
            "category",
            "category_name",
            "is_available",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_available", "created_at", "updated_at")

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
