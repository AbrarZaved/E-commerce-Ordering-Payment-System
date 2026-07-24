"""Shared pytest fixtures."""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.products.models import Category, Product

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="buyer@example.com", password="pass12345", full_name="Buyer")


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(email="admin@example.com", password="pass12345")


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def category_tree(db):
    root = Category.objects.create(name="Electronics", slug="electronics")
    computers = Category.objects.create(name="Computers", slug="computers", parent=root)
    laptops = Category.objects.create(name="Laptops", slug="laptops", parent=computers)
    accessories = Category.objects.create(name="Accessories", slug="accessories", parent=computers)
    return {"root": root, "computers": computers, "laptops": laptops, "accessories": accessories}


@pytest.fixture
def product(db, category_tree):
    return Product.objects.create(
        name="Ultrabook",
        sku="LAP-001",
        price=Decimal("1000.00"),
        stock=10,
        category=category_tree["laptops"],
    )
