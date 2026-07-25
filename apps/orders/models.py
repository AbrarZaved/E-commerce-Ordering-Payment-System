from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.products.models import Product


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    CANCELED = "canceled", "Canceled"


class Order(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="orders",
        on_delete=models.CASCADE,
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=16,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.status})"

    def calculate_total(self) -> Decimal:
        """Deterministic, side-effect-free total from related order items"""
        total = sum((item.subtotal for item in self.items.all()), Decimal("0.00"))
        return total.quantize(Decimal("0.01"))

    def recalculate_total(self, save: bool = True) -> Decimal:
        self.total_amount = self.calculate_total()
        if save:
            self.save(update_fields=["total_amount", "updated_at"])
        return self.total_amount

    @property
    def is_pending(self) -> bool:
        return self.status == OrderStatus.PENDING

    def mark_paid(self, save: bool = True) -> None:
        self.status = OrderStatus.PAID
        if save:
            self.save(update_fields=["status", "updated_at"])

    def mark_canceled(self, save: bool = True) -> None:
        self.status = OrderStatus.CANCELED
        if save:
            self.save(update_fields=["status", "updated_at"])


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    # Price snapshotted at order time so later price changes don't rewrite history.
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="uniq_product_per_order"),
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="orderitem_qty_positive"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_id} (order {self.order_id})"

    @property
    def subtotal(self) -> Decimal:
        """Deterministic line subtotal = price * quantity."""
        if self.price is None or self.quantity is None:
            return Decimal("0.00")
        return (self.price * self.quantity).quantize(Decimal("0.01"))
