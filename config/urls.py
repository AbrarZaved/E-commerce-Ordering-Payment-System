from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.views import HealthCheckView
from apps.core.views import HealthCheckView
from apps.users.views import AdminUserListView

api_v1 = [
    path("auth/", include("apps.users.urls")),
    path("admin/users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("", include("apps.products.urls")),
    path("", include("apps.cart.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.payments.urls")),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthCheckView.as_view(), name="health"),
    path("api/v1/", include((api_v1, "api"), namespace="v1")),
    # Webhooks are provider-facing and live outside the versioned/auth API.
    path("webhooks/", include("apps.payments.webhooks.urls")),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
