from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.serializers import OrderSerializer

from . import services
from .serializers import (
    AddCartItemSerializer,
    CartSerializer,
    MergeCartSerializer,
    UpdateCartItemSerializer,
)


def _cart_response(cart, status_code=200):
    return Response(CartSerializer(cart).data, status=status_code)


class CartView(APIView):
    """Retrieve the current user's persistent cart, or empty it."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = services.get_or_create_cart(request.user)
        return _cart_response(cart)

    def delete(self, request):
        cart = services.clear_cart(request.user)
        return _cart_response(cart)


class CartItemsView(APIView):
    """Add a product to the cart (or increment its quantity)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.add_to_cart(
            request.user,
            serializer.validated_data["product_id"],
            serializer.validated_data["quantity"],
        )
        return _cart_response(cart, status_code=201)


class CartItemDetailView(APIView):
    """Update or remove a single line item (keyed by product id)."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, product_id):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.set_quantity(
            request.user, product_id, serializer.validated_data["quantity"]
        )
        return _cart_response(cart)

    def delete(self, request, product_id):
        cart = services.remove_item(request.user, product_id)
        return _cart_response(cart)


class CartMergeView(APIView):
    """Merge a guest (client-side) cart into the server cart after login."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MergeCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.merge_items(request.user, serializer.validated_data["items"])
        return _cart_response(cart)


class CartCheckoutView(APIView):
    """Convert the cart into a pending order and empty the cart."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order = services.checkout_cart(request.user)
        return Response(OrderSerializer(order).data, status=201)
