from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.products.models import Product


class Cart(TimeStampedModel):
    """A persistent, per-user shopping cart"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="cart",
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"Cart(user={self.user_id})"

    def total_amount(self) -> Decimal:
        """Live total using each product's current price."""
        total = sum((item.subtotal for item in self.items.all()), Decimal("0.00"))
        return total.quantize(Decimal("0.01"))

    def item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="cart_items", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uniq_product_per_cart"),
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="cartitem_qty_positive"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_id} (cart {self.cart_id})"

    @property
    def subtotal(self) -> Decimal:
        """Live line subtotal using the product's current price."""
        if not getattr(self, "product_id", None) or self.quantity is None:
            return Decimal("0.00")
        return (self.product.price * self.quantity).quantize(Decimal("0.01"))
