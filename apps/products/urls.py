from django.urls import path

from .views import (
    CategoryDetailView,
    CategoryListCreateView,
    CategoryTreeView,
    ProductDetailView,
    ProductListCreateView,
    ProductRecommendationsView,
)

urlpatterns = [
    path("categories/", CategoryListCreateView.as_view(), name="category-list"),
    path("categories/tree/", CategoryTreeView.as_view(), name="category-tree"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="category-detail"),
    path("products/", ProductListCreateView.as_view(), name="product-list"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path(
        "products/<int:pk>/recommendations/",
        ProductRecommendationsView.as_view(),
        name="product-recommendations",
    ),
]
