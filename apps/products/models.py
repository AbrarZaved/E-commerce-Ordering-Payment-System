from django.db import models

from apps.core.models import TimeStampedModel


class Category(TimeStampedModel):
    """Self-referential hierarchical category tree."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="uniq_category_name_per_parent"),
        ]

    def __str__(self):
        return self.name


class ProductStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class Product(TimeStampedModel):
    name = models.CharField(max_length=255, db_index=True)
    sku = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=ProductStatus.choices,
        default=ProductStatus.ACTIVE,
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        related_name="products",
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "category"])]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_available(self):
        return self.status == ProductStatus.ACTIVE and self.stock > 0
