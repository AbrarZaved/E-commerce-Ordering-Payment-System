from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Category
from .services import invalidate_category_tree_cache


@receiver([post_save, post_delete], sender=Category)
def _invalidate_tree_cache(sender, **kwargs):
    """Any category create/update/delete invalidates the cached tree."""
    invalidate_category_tree_cache()
