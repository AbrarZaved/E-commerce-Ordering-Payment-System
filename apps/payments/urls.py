from django.urls import path

from .views import (
    AdminPaymentListView,
    PaymentCancelView,
    PaymentConfigView,
    PaymentConfirmView,
    PaymentDetailView,
    PaymentInitiateView,
    PaymentListView,
    PaymentResumeView,
    PaymentVerifyView,
)

urlpatterns = [
    path("payments/", PaymentListView.as_view(), name="payment-list"),
    path("payments/config/", PaymentConfigView.as_view(), name="payment-config"),
    path("payments/initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),
    path("payments/resume/", PaymentResumeView.as_view(), name="payment-resume"),
    path("payments/confirm/", PaymentConfirmView.as_view(), name="payment-confirm"),
    path("payments/<int:pk>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("payments/<int:pk>/verify/", PaymentVerifyView.as_view(), name="payment-verify"),
    path("payments/<int:pk>/cancel/", PaymentCancelView.as_view(), name="payment-cancel"),
    path("admin/payments/", AdminPaymentListView.as_view(), name="admin-payment-list"),
]