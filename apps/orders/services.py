"""Order creation and lifecycle services (kept out of views/serializers)."""
from __future__ import annotations

import logging

from django.db import transaction

from apps.core.exceptions import InsufficientStockError, InvalidOrderState
from apps.products.models import Product, ProductStatus

from .models import Order, OrderItem, OrderStatus

logger = logging.getLogger(__name__)


@transaction.atomic
def create_order(user, items: list[dict]) -> Order:
    # Creating a pending order.

    order = Order.objects.create(user=user, status=OrderStatus.PENDING)

    product_ids = [item["product_id"] for item in items]
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

    for item in items:
        product = products.get(item["product_id"])
        quantity = item["quantity"]
        if product is None or product.status != ProductStatus.ACTIVE:
            raise InvalidOrderState(f"Product {item['product_id']} is not available.")
        if quantity > product.stock:
            raise InsufficientStockError(
                f"Only {product.stock} unit(s) of '{product.name}' available."
            )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price,
        )

    order.recalculate_total()
    logger.info("order %s created for user %s total=%s", order.id, user.id, order.total_amount)
    return order


@transaction.atomic
def reduce_stock_for_order(order: Order) -> None:
    # Safely reducing stock for a paid order using row locks.

    for item in order.items.select_related("product"):
        product = Product.objects.select_for_update().get(pk=item.product_id)
        if item.quantity > product.stock:
            raise InsufficientStockError(
                f"Stock changed: only {product.stock} unit(s) of '{product.name}' left."
            )
        product.stock -= item.quantity
        product.save(update_fields=["stock", "updated_at"])
        logger.info("reduced stock product=%s by=%s -> %s", product.id, item.quantity, product.stock)
