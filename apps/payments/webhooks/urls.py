from django.urls import path

from .views import BkashWebhookView, StripeWebhookView

urlpatterns = [
    path("stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("bkash/", BkashWebhookView.as_view(), name="bkash-webhook"),
]
