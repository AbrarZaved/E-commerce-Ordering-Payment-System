"""Category-tree building, DFS traversal, and Redis caching"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from django.conf import settings
from django.core.cache import cache

from .models import Category, Product, ProductStatus

logger = logging.getLogger(__name__)


def _build_tree_from_db() -> list[dict]:
    """Build a nested category tree using a single query + DFS assembly."""
    categories = list(Category.objects.all().values("id", "name", "slug", "parent_id"))
    children_map: dict[int | None, list[dict]] = defaultdict(list)
    for cat in categories:
        children_map[cat["parent_id"]].append(cat)

    def attach(node: dict) -> dict:
        return {
            "id": node["id"],
            "name": node["name"],
            "slug": node["slug"],
            "children": [attach(child) for child in children_map.get(node["id"], [])],
        }

    roots = children_map.get(None, [])
    return [attach(root) for root in roots]


def get_category_tree(use_cache: bool = True) -> list[dict]:
    """Return the nested category tree, served from Redis when available."""
    if use_cache:
        cached = cache.get(settings.CATEGORY_TREE_CACHE_KEY)
        if cached is not None:
            logger.debug("category tree cache hit")
            return cached

    tree = _build_tree_from_db()
    if use_cache:
        cache.set(settings.CATEGORY_TREE_CACHE_KEY, tree, settings.CATEGORY_TREE_CACHE_TTL)
        logger.info("category tree rebuilt and cached")
    return tree


def invalidate_category_tree_cache() -> None:
    cache.delete(settings.CATEGORY_TREE_CACHE_KEY)
    logger.info("category tree cache invalidated")


def descendant_category_ids(root_id: int) -> list[int]:
    """Depth-first traversal returning ``root_id`` and all descendant ids"""
    edges = list(Category.objects.all().values_list("parent_id", "id"))
    children_map: dict[int | None, list[int]] = defaultdict(list)
    for parent_id, child_id in edges:
        children_map[parent_id].append(child_id)

    ordered: list[int] = []
    seen: set[int] = set()
    stack: list[int] = [root_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        ordered.append(current)
        # Push children in reverse so traversal visits them left-to-right.
        for child_id in reversed(children_map.get(current, [])):
            if child_id not in seen:
                stack.append(child_id)
    return ordered


def dfs_descendant_category_ids(root: Category) -> list[int]:
    """Backward-compatible wrapper that traverses from a ``Category`` instance."""
    return descendant_category_ids(root.id)


def recommended_products(product: Product, limit: int = 10) -> Iterable[Product]:
    # Recommending related products via DFS over the product's category subtree.

    if product.category is None:
        return Product.objects.none()

    root_cat = product.category
    while root_cat.parent_id is not None:
        root_cat = root_cat.parent

    category_ids = dfs_descendant_category_ids(root_cat)
    # Preserve DFS ordering as a relevance signal.
    ordering = {cat_id: index for index, cat_id in enumerate(category_ids)}

    candidates = list(
        Product.objects.filter(
            category_id__in=category_ids,
            status=ProductStatus.ACTIVE,
            stock__gt=0,
        ).exclude(id=product.id)
    )
    candidates.sort(key=lambda p: (ordering.get(p.category_id, 1_000_000), -p.created_at.timestamp()))
    return candidates[:limit]
