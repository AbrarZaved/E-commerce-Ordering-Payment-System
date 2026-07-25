from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(
    tags=["Health"],
    summary="System health check probe",
    responses={200: inline_serializer("HealthResponse", {"status": serializers.CharField()})},
)
class HealthCheckView(APIView):
    """Lightweight liveness probe."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})