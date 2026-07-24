from django.urls import path

from .views import (
    CartCheckoutView,
    CartItemDetailView,
    CartItemsView,
    CartMergeView,
    CartView,
)

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart-detail"),
    path("cart/items/", CartItemsView.as_view(), name="cart-items"),
    path("cart/items/<int:product_id>/", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("cart/merge/", CartMergeView.as_view(), name="cart-merge"),
    path("cart/checkout/", CartCheckoutView.as_view(), name="cart-checkout"),
]
