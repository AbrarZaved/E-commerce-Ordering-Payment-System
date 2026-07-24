from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import DefaultPagination
from apps.core.permissions import IsOwner

from .models import Order
from .serializers import OrderCreateSerializer, OrderSerializer
from .services import create_order


class OrderListCreateView(APIView):
    """Users can create and list only their own orders."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects.filter(user=request.user)
            .prefetch_related("items__product")
            .all()
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        return paginator.get_paginated_response(OrderSerializer(page, many=True).data)

    def post(self, request):
        input_serializer = OrderCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        order = create_order(request.user, input_serializer.validated_data["items"])
        return Response(OrderSerializer(order).data, status=201)


class OrderDetailView(APIView):
    """Retrieve a single order owned by the requesting user."""

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request, pk):
        order = get_object_or_404(
            Order.objects.prefetch_related("items__product"), pk=pk
        )
        self.check_object_permissions(request, order)
        return Response(OrderSerializer(order).data)
