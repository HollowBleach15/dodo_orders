from decimal import Decimal
from datetime import date, timedelta
from typing import Optional
from django.db.models import Sum, Count, Avg, F, DecimalField
from django.db.models.functions import TruncDate, TruncHour
from django.core.cache import cache

from core.models import Order, OrderItem, Client


class RevenueReport:
    """Отчёт по выручке."""

    @staticmethod
    def daily_revenue(date_from: date, date_to: date, branch_id: Optional[int] = None) -> dict:
        qs = Order.objects.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
            status="done",
        )
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        agg = qs.aggregate(
            orders_count=Count("id"),
            revenue=Sum("total"),
            avg_check=Avg("total"),
        )
        return {
            "orders_count": agg["orders_count"] or 0,
            "revenue": agg["revenue"] or Decimal("0"),
            "avg_check": (agg["avg_check"] or Decimal("0")).quantize(Decimal("0.01")),
            "date_from": date_from,
            "date_to": date_to,
        }

    @staticmethod
    def revenue_by_day(date_from: date, date_to: date):
        return list(
            Order.objects.filter(
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
                status="done",
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(revenue=Sum("total"), orders=Count("id"))
            .order_by("day")
        )

    @staticmethod
    def revenue_by_branch(date_from: date, date_to: date):
        return list(
            Order.objects.filter(
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
                status="done",
            )
            .values("branch__name")
            .annotate(revenue=Sum("total"), orders=Count("id"),
                      avg_check=Avg("total"))
            .order_by("-revenue")
        )

    @staticmethod
    def revenue_by_hour(date_from: date, date_to: date):
        """Загрузка по часам для прогноза смен."""
        return list(
            Order.objects.filter(
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            )
            .annotate(hour=TruncHour("created_at"))
            .values("hour")
            .annotate(orders=Count("id"))
            .order_by("hour")
        )


class ProductReport:
    """Отчёт по ассортименту."""

    @staticmethod
    def top_products(date_from: date, date_to: date, limit: int = 20):
        cache_key = f"top_products:{date_from}:{date_to}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = list(
            OrderItem.objects.filter(
                order__created_at__date__gte=date_from,
                order__created_at__date__lte=date_to,
                order__status="done",
            )
            .values("product__id", "product__name", "product__category")
            .annotate(
                qty_sold=Sum("quantity"),
                revenue=Sum(F("quantity") * F("price"),
                            output_field=DecimalField(max_digits=12, decimal_places=2)),
            )
            .order_by("-qty_sold")[:limit]
        )
        cache.set(cache_key, result, timeout=300)  # 5 минут
        return result

    @staticmethod
    def revenue_by_category(date_from: date, date_to: date):
        return list(
            OrderItem.objects.filter(
                order__created_at__date__gte=date_from,
                order__created_at__date__lte=date_to,
                order__status="done",
            )
            .values("product__category")
            .annotate(
                qty=Sum("quantity"),
                revenue=Sum(F("quantity") * F("price"),
                            output_field=DecimalField(max_digits=12, decimal_places=2)),
            )
            .order_by("-revenue")
        )


class ClientReport:
    """Клиентская аналитика."""

    @staticmethod
    def top_clients(date_from: date, date_to: date, limit: int = 20):
        return list(
            Client.objects.filter(
                orders__created_at__date__gte=date_from,
                orders__created_at__date__lte=date_to,
                orders__status="done",
            )
            .annotate(
                orders_total=Count("orders"),
                revenue=Sum("orders__total"),
            )
            .order_by("-revenue")[:limit]
            .values("id", "full_name", "phone", "orders_total", "revenue")
        )

    @staticmethod
    def inactive_clients(days: int = 60):
        """Клиенты, не делавшие заказов более N дней."""
        threshold = date.today() - timedelta(days=days)
        return Client.objects.filter(is_active=True).exclude(
            orders__created_at__date__gte=threshold
        ).distinct()

    @staticmethod
    def cancellation_rate(date_from: date, date_to: date) -> dict:
        qs = Order.objects.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        total = qs.count()
        cancelled = qs.filter(status="cancelled").count()
        rate = (cancelled / total * 100) if total else 0
        return {"total": total, "cancelled": cancelled, "rate": round(rate, 2)}
