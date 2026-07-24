from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.orders.models import Order


class PaymentProvider(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    BKASH = "bkash", "bKash"


class PaymentStatus(models.TextChoices):
    INITIATED = "initiated", "Initiated"
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELED = "canceled", "Canceled"


class Payment(TimeStampedModel):
    # order is nullable: for the storefront flow the order is created ONLY after
    # the payment succeeds, so a failed/abandoned checkout never records one.
    order = models.ForeignKey(
        Order, related_name="payments", on_delete=models.CASCADE, null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="payments",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    # Cart snapshot captured at initiation (list of {"product_id", "quantity"})
    # so the order can be built at success time without a pre-existing order.
    items_snapshot = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    # transaction_id is provider's reference; unique but nullable until assigned.
    transaction_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["provider", "status"])]

    def __str__(self):
        return f"Payment #{self.pk} {self.provider} {self.status}"

    @property
    def is_successful(self) -> bool:
        return self.status == PaymentStatus.SUCCEEDED
