"""Tests for DFS traversal + recommendations + category tree caching."""
from decimal import Decimal

import pytest

from apps.products.models import Product
from apps.products.services import (
    dfs_descendant_category_ids,
    get_category_tree,
    recommended_products,
)


@pytest.mark.django_db
def test_dfs_returns_root_and_all_descendants(category_tree):
    ids = dfs_descendant_category_ids(category_tree["root"])
    expected = {
        category_tree["root"].id,
        category_tree["computers"].id,
        category_tree["laptops"].id,
        category_tree["accessories"].id,
    }
    assert set(ids) == expected
    # Root must come first in a DFS pre-order.
    assert ids[0] == category_tree["root"].id


@pytest.mark.django_db
def test_dfs_leaf_returns_only_self(category_tree):
    ids = dfs_descendant_category_ids(category_tree["laptops"])
    assert ids == [category_tree["laptops"].id]


@pytest.mark.django_db
def test_recommendations_pull_from_subtree(category_tree, product):
    sibling = Product.objects.create(
        name="USB Hub", sku="ACC-001", price=Decimal("20.00"), stock=5,
        category=category_tree["accessories"],
    )
    recs = list(recommended_products(product))
    assert sibling in recs
    assert product not in recs


@pytest.mark.django_db
def test_recommendations_exclude_out_of_stock(category_tree, product):
    Product.objects.create(
        name="Sold Out", sku="ACC-009", price=Decimal("20.00"), stock=0,
        category=category_tree["accessories"],
    )
    recs = list(recommended_products(product))
    assert all(p.stock > 0 for p in recs)


@pytest.mark.django_db
def test_category_tree_structure(category_tree):
    tree = get_category_tree(use_cache=False)
    assert len(tree) == 1
    assert tree[0]["name"] == "Electronics"
    assert tree[0]["children"][0]["name"] == "Computers"
