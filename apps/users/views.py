from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import DefaultPagination

from .serializers import (
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(APIView):
    """Public registration endpoint."""

    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    @extend_schema(
        tags=["Auth"],
        summary="Register a new user account",
        request=RegisterSerializer,
        responses={201: RegisterSerializer},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


class LoginView(APIView):
    """JWT login (email + password) returning access/refresh tokens."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = EmailTokenObtainPairSerializer

    @extend_schema(
        tags=["Auth"],
        summary="Log in with email and password",
        request=EmailTokenObtainPairSerializer,
    )
    def post(self, request):
        serializer = EmailTokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=200)


class MeView(APIView):
    """Return the currently authenticated user."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(
        tags=["Users"],
        summary="Get current user profile",
        responses={200: UserSerializer},
    )
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class AdminUserListView(APIView):
    """Staff-only: list every registered user (for the admin panel)."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = UserSerializer

    @extend_schema(
        tags=["Admin Users"],
        summary="List all registered users (Admin)",
        responses={200: UserSerializer(many=True)},
    )
    def get(self, request):
        users = User.objects.all().order_by("-date_joined")
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(users, request, view=self)
        return paginator.get_paginated_response(UserSerializer(page, many=True).data)