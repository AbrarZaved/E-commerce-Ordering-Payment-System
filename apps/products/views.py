from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import DefaultPagination
from apps.core.permissions import IsAdminOrReadOnly

from .filters import ProductFilter
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    ProductSerializer,
)
from .services import get_category_tree, recommended_products

ORDERING_WHITELIST = {"price", "-price", "created_at", "-created_at", "name", "-name"}


class CategoryListCreateView(APIView):
    """List all categories or create one (admin-only writes)."""

    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        categories = Category.objects.all()
        return Response(CategorySerializer(categories, many=True).data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


class CategoryDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self, pk):
        obj = get_object_or_404(Category, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    def get(self, request, pk):
        return Response(CategorySerializer(self.get_object(pk)).data)

    def put(self, request, pk):
        serializer = CategorySerializer(self.get_object(pk), data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, pk):
        serializer = CategorySerializer(self.get_object(pk), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        self.get_object(pk).delete()
        return Response(status=204)


class CategoryTreeView(APIView):
    """Return the full nested category tree (Redis-cached)."""

    permission_classes = [AllowAny]

    @extend_schema(responses=CategoryTreeSerializer(many=True))
    def get(self, request):
        return Response(get_category_tree())


class ProductListCreateView(APIView):
    """Public paginated/filterable list; admin-only create."""

    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        queryset = Product.objects.select_related("category").all()
        # Filtering (django-filter)
        queryset = ProductFilter(request.query_params, queryset=queryset).qs
        # Search
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(sku__icontains=search)
                | Q(description__icontains=search)
            )
        # Ordering
        ordering = request.query_params.get("ordering")
        if ordering in ORDERING_WHITELIST:
            queryset = queryset.order_by(ordering)
        # Pagination
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


class ProductDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self, pk):
        obj = get_object_or_404(Product.objects.select_related("category"), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    def get(self, request, pk):
        return Response(ProductSerializer(self.get_object(pk)).data)

    def put(self, request, pk):
        serializer = ProductSerializer(self.get_object(pk), data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, pk):
        serializer = ProductSerializer(self.get_object(pk), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        self.get_object(pk).delete()
        return Response(status=204)


class ProductRecommendationsView(APIView):
    """Related products found via DFS over the category subtree."""

    permission_classes = [AllowAny]

    @extend_schema(responses=ProductSerializer(many=True))
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        products = recommended_products(product)
        return Response(ProductSerializer(products, many=True).data)
