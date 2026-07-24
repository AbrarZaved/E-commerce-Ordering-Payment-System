from django.urls import path

from .views import (
    PaymentCancelView,
    PaymentConfigView,
    PaymentConfirmView,
    PaymentDetailView,
    PaymentInitiateView,
    PaymentListView,
    PaymentVerifyView,
)
urlpatterns = [
    path("payments/", PaymentListView.as_view(), name="payment-list"),
    path("payments/config/", PaymentConfigView.as_view(), name="payment-config"),
    path("payments/initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),
    path("payments/confirm/", PaymentConfirmView.as_view(), name="payment-confirm"),
    path("payments/<int:pk>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("payments/<int:pk>/verify/", PaymentVerifyView.as_view(), name="payment-verify"),
    path("payments/<int:pk>/cancel/", PaymentCancelView.as_view(), name="payment-cancel"),
]