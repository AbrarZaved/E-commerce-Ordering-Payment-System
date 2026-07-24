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
    order = models.ForeignKey(Order, related_name="payments", on_delete=models.CASCADE)
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
