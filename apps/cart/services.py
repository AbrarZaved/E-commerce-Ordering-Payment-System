"""Cart mutation services (business logic kept out of views/serializers)."""
from __future__ import annotations

import logging

from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.exceptions import InsufficientStockError, InvalidOrderState
from apps.orders.services import create_order
from apps.products.models import Product, ProductStatus

from .models import Cart, CartItem

logger = logging.getLogger(__name__)


def get_or_create_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _active_product(product_id: int) -> Product:
    product = get_object_or_404(Product, pk=product_id)
    if product.status != ProductStatus.ACTIVE:
        raise InvalidOrderState(f"Product '{product.name}' is not available.")
    return product


def _assert_stock(product: Product, quantity: int) -> None:
    if quantity > product.stock:
        raise InsufficientStockError(
            f"Only {product.stock} unit(s) of '{product.name}' available."
        )


@transaction.atomic
def add_to_cart(user, product_id: int, quantity: int = 1) -> Cart:
    """Add a product (or increment its quantity) in the user's cart."""
    product = _active_product(product_id)
    cart = get_or_create_cart(user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": quantity}
    )
    new_quantity = quantity if created else item.quantity + quantity
    _assert_stock(product, new_quantity)
    item.quantity = new_quantity
    item.save(update_fields=["quantity", "updated_at"])
    logger.info("cart add user=%s product=%s qty=%s", user.id, product_id, new_quantity)
    return cart


@transaction.atomic
def set_quantity(user, product_id: int, quantity: int) -> Cart:
    """Set an absolute quantity for a line item; quantity 0 removes it."""
    cart = get_or_create_cart(user)
    if quantity == 0:
        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
        return cart
    product = _active_product(product_id)
    _assert_stock(product, quantity)
    item, _ = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": quantity}
    )
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return cart


@transaction.atomic
def remove_item(user, product_id: int) -> Cart:
    cart = get_or_create_cart(user)
    CartItem.objects.filter(cart=cart, product_id=product_id).delete()
    return cart


@transaction.atomic
def clear_cart(user) -> Cart:
    cart = get_or_create_cart(user)
    cart.items.all().delete()
    return cart


@transaction.atomic
def merge_items(user, items: list[dict]) -> Cart:
    """Merge a guest (client-side) cart into the user's server cart on login.

    Quantities are added to any existing lines and clamped to available stock
    so a stale guest cart can never block login/merge.
    """
    cart = get_or_create_cart(user)
    products = {
        p.id: p
        for p in Product.objects.filter(
            id__in=[i["product_id"] for i in items], status=ProductStatus.ACTIVE
        )
    }
    for entry in items:
        product = products.get(entry["product_id"])
        if product is None:
            continue
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": 0}
        )
        merged = (0 if created else item.quantity) + entry["quantity"]
        item.quantity = min(merged, product.stock) or 1
        if item.quantity > product.stock:
            item.quantity = product.stock
        if item.quantity <= 0:
            item.delete()
            continue
        item.save(update_fields=["quantity", "updated_at"])
    logger.info("cart merge user=%s incoming=%s", user.id, len(items))
    return cart


@transaction.atomic
def checkout_cart(user):
    """Convert the cart into a pending Order, then empty the cart."""
    cart = get_or_create_cart(user)
    items = list(cart.items.select_related("product").all())
    if not items:
        raise InvalidOrderState("Your cart is empty.")
    payload = [{"product_id": i.product_id, "quantity": i.quantity} for i in items]
    order = create_order(user, payload)
    cart.items.all().delete()
    logger.info("cart checkout user=%s order=%s", user.id, order.id)
    return order
