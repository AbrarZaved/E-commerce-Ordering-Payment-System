"""Async payment tasks (Celery)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_webhook_event(self, provider: str, payload: dict):
    # Processing a pre-validated webhook payload asynchronously.


    from .models import Payment
    from .service import PaymentService

    transaction_id = payload.get("transaction_id")
    try:
        payment = Payment.objects.get(transaction_id=transaction_id, provider=provider)
    except Payment.DoesNotExist:
        logger.warning("async webhook: unknown transaction %s", transaction_id)
        return

    service = PaymentService(provider)
    service._apply_result(payment, payload["status"], payload.get("raw", {}), transaction_id)
    logger.info("async webhook processed payment=%s status=%s", payment.id, payload["status"])


@shared_task
def send_order_confirmation_email(order_id: int):
    """Send an order confirmation email (stubbed via console backend)."""
    from django.core.mail import send_mail

    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("user").get(pk=order_id)
    except Order.DoesNotExist:
        return
    send_mail(
        subject=f"Order #{order.id} confirmed",
        message=f"Your order #{order.id} for {order.total_amount} has been paid. Thank you!",
        from_email=None,
        recipient_list=[order.user.email],
        fail_silently=True,
    )
