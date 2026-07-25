"""Async payment tasks (Celery)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_webhook_event(self, provider: str, payload: dict):
    """Process a pre-validated webhook payload asynchronously."""
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
def expire_pending_payment(payment_id: int):
    """Countdown task scheduled at initiation time.

    Fails a single payment if it is still pending when the countdown fires.
    """
    from .models import Payment, PaymentStatus
    from .service import PaymentService

    try:
        payment = Payment.objects.get(pk=payment_id)
    except Payment.DoesNotExist:
        return

    if payment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED, PaymentStatus.CANCELED):
        return

    PaymentService(payment.provider).expire(payment)
    logger.info("payment %s expired (pending timeout)", payment_id)


@shared_task
def expire_stale_payments():
    """Periodic sweep (Celery beat): fail every payment past its ``expires_at``.

    Safety net in case a countdown task was lost (e.g. worker restart).
    """
    from django.utils import timezone

    from .models import Payment, PaymentStatus
    from .service import PaymentService

    now = timezone.now()
    stale = Payment.objects.filter(
        status__in=[PaymentStatus.INITIATED, PaymentStatus.PENDING],
        expires_at__isnull=False,
        expires_at__lt=now,
    )
    count = 0
    for payment in stale:
        PaymentService(payment.provider).expire(payment)
        count += 1
    if count:
        logger.info("expire_stale_payments: failed %s stale payment(s)", count)
    return count


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