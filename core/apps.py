from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _register_periodic_tasks(sender, **kwargs):
    """Создаём периодические задачи один раз после миграций."""
    from django_celery_beat.models import (
        PeriodicTask, IntervalSchedule, CrontabSchedule,
    )

    interval, _ = IntervalSchedule.objects.get_or_create(
        every=30, period=IntervalSchedule.MINUTES,
    )
    PeriodicTask.objects.get_or_create(
        name="auto-cancel-stale",
        task="core.tasks.auto_cancel_stale_orders",
        defaults={"interval": interval},
    )

    crontab, _ = CrontabSchedule.objects.get_or_create(hour=9, minute=0)
    PeriodicTask.objects.get_or_create(
        name="daily-summary",
        task="core.tasks.send_daily_summary",
        defaults={"crontab": crontab},
    )


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Учёт заказов"

    def ready(self):
        post_migrate.connect(_register_periodic_tasks, sender=self)