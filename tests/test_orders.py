"""Unit tests for order/model business logic."""
from decimal import Decimal

import pytest

from apps.core.exceptions import InsufficientStockError
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.orders.services import create_order, reduce_stock_for_order


@pytest.mark.django_db
def test_order_total_calculation(user, product):
    order = Order.objects.create(user=user)
    OrderItem.objects.create(order=order, product=product, quantity=2, price=Decimal("1000.00"))
    assert order.calculate_total() == Decimal("2000.00")
    order.recalculate_total()
    assert order.total_amount == Decimal("2000.00")


@pytest.mark.django_db
def test_orderitem_subtotal(user, product):
    order = Order.objects.create(user=user)
    item = OrderItem.objects.create(order=order, product=product, quantity=3, price=Decimal("9.99"))
    assert item.subtotal == Decimal("29.97")


@pytest.mark.django_db
def test_create_order_rejects_insufficient_stock(user, product):
    with pytest.raises(InsufficientStockError):
        create_order(user, [{"product_id": product.id, "quantity": product.stock + 5}])


@pytest.mark.django_db
def test_reduce_stock_reduces_inventory(user, product):
    order = create_order(user, [{"product_id": product.id, "quantity": 3}])
    reduce_stock_for_order(order)
    product.refresh_from_db()
    assert product.stock == 7


@pytest.mark.django_db
def test_create_order_sets_pending(user, product):
    order = create_order(user, [{"product_id": product.id, "quantity": 1}])
    assert order.status == OrderStatus.PENDING
    assert order.total_amount == Decimal("1000.00")
