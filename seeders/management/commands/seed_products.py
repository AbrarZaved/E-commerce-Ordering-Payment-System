from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.products.models import Category, Product, ProductStatus

# Hierarchical category tree so DFS/recommendations have something to traverse.
CATEGORY_TREE = {
    "Electronics": {
        "Computers": {"Laptops": {}, "Accessories": {}},
        "Phones": {},
    },
    "Home": {
        "Kitchen": {},
        "Furniture": {},
    },
}

PRODUCTS = [
    ("Ultrabook Pro 14", "LAP-001", "Laptops", "1599.00", 12),
    ("Budget Notebook 15", "LAP-002", "Laptops", "749.00", 25),
    ("USB-C Hub 7-in-1", "ACC-001", "Accessories", "49.99", 100),
    ("Wireless Mouse", "ACC-002", "Accessories", "24.50", 200),
    ("Mechanical Keyboard", "ACC-003", "Accessories", "89.00", 60),
    ("Smartphone X", "PHN-001", "Phones", "999.00", 40),
    ("Smartphone Lite", "PHN-002", "Phones", "399.00", 80),
    ("Chef's Knife 8in", "KIT-001", "Kitchen", "59.00", 45),
    ("Nonstick Pan Set", "KIT-002", "Kitchen", "79.00", 30),
    ("Ergonomic Chair", "FUR-001", "Furniture", "229.00", 15),
    ("Standing Desk", "FUR-002", "Furniture", "349.00", 10),
    ("Laptop Sleeve 14in", "ACC-004", "Accessories", "19.99", 150),
    ("Noise-Cancelling Headphones", "ACC-005", "Accessories", "199.00", 35),
]


class Command(BaseCommand):
    help = "Seed sample categories (hierarchical) and products."

    def handle(self, *args, **options):
        name_to_category = {}

        def create_tree(subtree, parent=None):
            for name, children in subtree.items():
                category, _ = Category.objects.get_or_create(
                    name=name,
                    parent=parent,
                    defaults={"slug": slugify(f"{name}-{parent.id if parent else 'root'}")},
                )
                name_to_category[name] = category
                create_tree(children, category)

        create_tree(CATEGORY_TREE)

        created = 0
        for name, sku, category_name, price, stock in PRODUCTS:
            _, was_created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "description": f"Sample product: {name}.",
                    "price": Decimal(price),
                    "stock": stock,
                    "status": ProductStatus.ACTIVE,
                    "category": name_to_category.get(category_name),
                },
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Category.objects.count()} categories, {created} new products."
            )
        )
