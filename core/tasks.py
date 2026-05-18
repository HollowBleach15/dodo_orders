import logging
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_client_about_status(self, order_id: int):
    from .models import Order
    try:
        order = Order.objects.select_related("client").get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("Заказ #%s не найден — задача отменена", order_id)
        return

    if not order.client.email:
        logger.info("Клиент %s без email — пропуск", order.client.pk)
        return

    status_display: str = order.get_status_display()  # type: ignore[attr-defined]

    try:
        send_mail(
            subject=f"Заказ #{order.pk}: {status_display}",
            message=(
                f"Здравствуйте, {order.client.full_name}!\n\n"
                f"Статус вашего заказа #{order.pk}: {status_display}.\n"
                f"Сумма: {order.total} ₽.\n\n"
                f"С уважением, Додо Франчайзинг."
            ),
            from_email="noreply@dodo-franchise.ru",
            recipient_list=[order.client.email],
            fail_silently=False,
        )
        logger.info("Уведомление по заказу #%s отправлено", order_id)
    except Exception as exc:
        logger.error("Ошибка отправки уведомления: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def auto_cancel_stale_orders():
    from .models import Order
    from .services import OrderService
    threshold = timezone.now() - timedelta(hours=2)
    stale = Order.objects.filter(status="new", created_at__lt=threshold)
    count = 0
    for order in stale:
        try:
            OrderService.change_status(order, "cancelled")
            try:
                notify_client_about_status.delay(order.pk)
            except Exception as exc:
                logger.warning("Не удалось поставить задачу уведомления для #%s: %s", order.pk, exc)
            count += 1
        except ValueError as e:
            logger.warning("Не удалось отменить заказ #%s: %s", order.pk, e)
    logger.info("Авто-отменено заказов: %s", count)
    return count


@shared_task
def send_daily_summary():
    from django.contrib.auth.models import User
    from reports.services import RevenueReport
    today = timezone.now().date()
    data = RevenueReport.daily_revenue(today, today)

    admins: list[User] = list(
        User.objects.filter(is_superuser=True).exclude(email="")
    )
    for admin in admins:
        send_mail(
            subject=f"Сводка за {today.strftime('%d.%m.%Y')}",
            message=(
                f"Заказов: {data['orders_count']}\n"
                f"Выручка: {data['revenue']} ₽\n"
                f"Средний чек: {data['avg_check']} ₽"
            ),
            from_email="noreply@dodo-franchise.ru",
            recipient_list=[admin.email],
            fail_silently=True,
        )
    return f"Отправлено {len(admins)} писем"