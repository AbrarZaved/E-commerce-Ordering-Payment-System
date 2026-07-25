from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import DefaultPagination
from apps.core.permissions import IsOwner

from .models import Order, OrderStatus
from .serializers import OrderCreateSerializer, OrderSerializer
from .services import create_order


class OrderListCreateView(APIView):
    """Users can create and list only their own orders."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    @extend_schema(
        tags=["Orders"],
        summary="List current user's orders",
        responses={200: OrderSerializer(many=True)},
    )
    def get(self, request):
        orders = (
            Order.objects.filter(user=request.user)
            .prefetch_related("items__product")
            .all()
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        return paginator.get_paginated_response(OrderSerializer(page, many=True).data)

    @extend_schema(
        tags=["Orders"],
        summary="Create a new order",
        request=OrderCreateSerializer,
        responses={201: OrderSerializer},
    )
    def post(self, request):
        input_serializer = OrderCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        order = create_order(request.user, input_serializer.validated_data["items"])
        return Response(OrderSerializer(order).data, status=201)


class OrderDetailView(APIView):
    """Retrieve a single order owned by the requesting user."""

    permission_classes = [permissions.IsAuthenticated, IsOwner]
    serializer_class = OrderSerializer

    @extend_schema(
        tags=["Orders"],
        summary="Retrieve single order by ID",
        responses={200: OrderSerializer},
    )
    def get(self, request, pk):
        order = get_object_or_404(
            Order.objects.prefetch_related("items__product"), pk=pk
        )
        self.check_object_permissions(request, order)
        return Response(OrderSerializer(order).data)


class AdminOrderListView(APIView):
    """Staff-only: list every order in the system (for the admin panel)."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = OrderSerializer

    @extend_schema(
        tags=["Admin Orders"],
        summary="List all orders across all users (Admin)",
        responses={200: OrderSerializer(many=True)},
    )
    def get(self, request):
        orders = (
            Order.objects.select_related("user")
            .prefetch_related("items__product")
            .all()
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        return paginator.get_paginated_response(OrderSerializer(page, many=True).data)


class AdminOrderDetailView(APIView):
    """Staff-only: view or update the status of any order."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = OrderSerializer

    @extend_schema(
        tags=["Admin Orders"],
        summary="Retrieve any order by ID (Admin)",
        responses={200: OrderSerializer},
    )
    def get(self, request, pk):
        order = get_object_or_404(
            Order.objects.prefetch_related("items__product"), pk=pk
        )
        return Response(OrderSerializer(order).data)

    @extend_schema(
        tags=["Admin Orders"],
        summary="Update order status (Admin)",
        request=inline_serializer("UpdateOrderStatus", {"status": serializers.ChoiceField(choices=OrderStatus.choices)}),
        responses={200: OrderSerializer},
    )
    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        status_value = request.data.get("status")
        valid = {choice for choice, _ in OrderStatus.choices}
        if status_value not in valid:
            return Response(
                {"error": {"message": "Invalid status. Choose pending, paid, or canceled."}},
                status=400,
            )
        order.status = status_value
        order.save(update_fields=["status", "updated_at"])
        return Response(OrderSerializer(order).data)
