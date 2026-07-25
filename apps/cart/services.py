"""Cart mutation services (business logic kept out of views/serializers)."""
from __future__ import annotations

import logging
from decimal import Decimal

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
    """Merging a guest (client-side) cart into the user's server cart on login"""
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
        existing = CartItem.objects.filter(cart=cart, product=product).first()
        current = existing.quantity if existing else 0

        # Clamp the merged quantity to available stock. Skip non-positive lines
        merged = min(current + entry["quantity"], product.stock)
        if merged <= 0:
            if existing:
                existing.delete()
            continue
        if existing:
            existing.quantity = merged
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            CartItem.objects.create(cart=cart, product=product, quantity=merged)
    logger.info("cart merge user=%s incoming=%s", user.id, len(items))
    return cart

@transaction.atomic
def snapshot_cart(user):
    # Validate the cart and return ``(items, total_amount)`` WITHOUT creating an order.
    cart = get_or_create_cart(user)
    items = list(cart.items.select_related("product").all())
    if not items:
        raise InvalidOrderState("Your cart is empty.")
    snapshot = []
    total = Decimal("0.00")
    for item in items:
        product = item.product
        if product.status != ProductStatus.ACTIVE:
            raise InvalidOrderState(f"Product '{product.name}' is not available.")
        _assert_stock(product, item.quantity)
        snapshot.append({"product_id": product.id, "quantity": item.quantity})
        total += product.price * item.quantity
    return snapshot, total.quantize(Decimal("0.01"))

@transaction.atomic
def checkout_cart(user):
    """Convert the cart into a pending Order, then empty the cart."""
    cart = get_or_create_cart(user)
    items = list(cart.items.select_related("product").all())
    if not items:
        raise InvalidOrderState("Your cart is empty.")
    payload = [{"product_id": i.product_id, "quantity": i.quantity} for i in items]
    order = create_order(user, payload)
    clear_cart(user)
    logger.info("cart checkout user=%s order=%s", user.id, order.id)
    return order
