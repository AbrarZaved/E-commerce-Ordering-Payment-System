import django_filters as filters

from .models import Product


class ProductFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = filters.NumberFilter(method="filter_category")
    in_stock = filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ["status", "category", "min_price", "max_price", "in_stock"]

    def filter_category(self, queryset, name, value):
        """Filter by a category *and all of its descendants*.

        Selecting a parent category (e.g. "Electronics") should surface every
        product in its subtree ("Computers", "Laptops", ...), not just products
        assigned directly to that parent node. Descendant ids come from a DFS
        walk of the category tree (see services.descendant_category_ids).
        """
        from .services import descendant_category_ids

        ids = descendant_category_ids(int(value))
        return queryset.filter(category_id__in=ids)

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset
