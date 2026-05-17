from decimal import Decimal
from datetime import date, datetime, time, timedelta
from django.test import TestCase
from django.utils import timezone

from core.models import Client, Branch, Product, Order, OrderItem
from reports.services import RevenueReport, ProductReport, ClientReport


class ReportsBaseTestCase(TestCase):
    """Готовит выборку заказов для тестов отчётности."""

    @classmethod
    def setUpTestData(cls):
        cls.today = date.today()
        cls.yesterday = cls.today - timedelta(days=1)

        cls.client_a = Client.objects.create(full_name="Клиент A", phone="+70000000001")
        cls.client_b = Client.objects.create(full_name="Клиент B", phone="+70000000002")

        cls.branch1 = Branch.objects.create(name="Филиал 1", address="addr1")
        cls.branch2 = Branch.objects.create(name="Филиал 2", address="addr2")

        cls.pizza = Product.objects.create(name="Маргарита", category="pizza", price=Decimal("500"))
        cls.drink = Product.objects.create(name="Кола", category="drink", price=Decimal("100"))

        # Заказ 1: вчера, филиал 1, выполнен, клиент A, 2 пиццы + 1 кола = 1100
        cls.o1 = cls._make_order(cls.client_a, cls.branch1, "done",
                                 [(cls.pizza, 2), (cls.drink, 1)], cls.yesterday)
        # Заказ 2: сегодня, филиал 1, выполнен, клиент A, 1 пицца = 500
        cls.o2 = cls._make_order(cls.client_a, cls.branch1, "done",
                                 [(cls.pizza, 1)], cls.today)
        # Заказ 3: сегодня, филиал 2, выполнен, клиент B, 3 пиццы = 1500
        cls.o3 = cls._make_order(cls.client_b, cls.branch2, "done",
                                 [(cls.pizza, 3)], cls.today)
        # Заказ 4: сегодня, филиал 1, отменён — не должен попадать в выручку
        cls.o4 = cls._make_order(cls.client_a, cls.branch1, "cancelled",
                                 [(cls.pizza, 10)], cls.today)

    @staticmethod
    def _make_order(client, branch, status, items, on_date):
        order = Order.objects.create(client=client, branch=branch, status=status)
        for product, qty in items:
            OrderItem.objects.create(order=order, product=product,
                                     quantity=qty, price=product.price)
        order.recalc_total()
        order.save()
        # Принудительно ставим дату создания
        dt = timezone.make_aware(datetime.combine(on_date, time.min))
        Order.objects.filter(pk=order.pk).update(created_at=dt)
        order.refresh_from_db()
        return order


class RevenueReportTests(ReportsBaseTestCase):

    def test_daily_revenue_total(self):
        result = RevenueReport.daily_revenue(self.yesterday, self.today)
        # Выполненные: o1(1100) + o2(500) + o3(1500) = 3100; заказов 3
        self.assertEqual(result["orders_count"], 3)
        self.assertEqual(result["revenue"], Decimal("3100.00"))

    def test_daily_revenue_excludes_cancelled(self):
        result = RevenueReport.daily_revenue(self.today, self.today)
        # Только o2(500) + o3(1500) = 2000; o4 отменён — игнор
        self.assertEqual(result["orders_count"], 2)
        self.assertEqual(result["revenue"], Decimal("2000.00"))

    def test_daily_revenue_filtered_by_branch(self):
        result = RevenueReport.daily_revenue(
            self.yesterday, self.today, branch_id=self.branch1.pk
        )
        # Филиал 1: o1(1100) + o2(500) = 1600
        self.assertEqual(result["orders_count"], 2)
        self.assertEqual(result["revenue"], Decimal("1600.00"))

    def test_avg_check_calculation(self):
        result = RevenueReport.daily_revenue(self.yesterday, self.today)
        # 3100 / 3 = 1033.33
        self.assertEqual(result["avg_check"], Decimal("1033.33"))

    def test_revenue_by_day(self):
        result = RevenueReport.revenue_by_day(self.yesterday, self.today)
        self.assertEqual(len(result), 2)
        # Вчера: 1100; сегодня: 2000
        day_map = {r["day"]: r["revenue"] for r in result}
        self.assertEqual(day_map[self.yesterday], Decimal("1100.00"))
        self.assertEqual(day_map[self.today], Decimal("2000.00"))

    def test_revenue_by_branch(self):
        result = RevenueReport.revenue_by_branch(self.yesterday, self.today)
        self.assertEqual(len(result), 2)
        # Сортировка по убыванию выручки
        self.assertEqual(result[0]["branch__name"], "Филиал 1")
        self.assertEqual(result[0]["revenue"], Decimal("1600.00"))
        self.assertEqual(result[1]["branch__name"], "Филиал 2")
        self.assertEqual(result[1]["revenue"], Decimal("1500.00"))

    def test_empty_period(self):
        future = self.today + timedelta(days=10)
        result = RevenueReport.daily_revenue(future, future)
        self.assertEqual(result["orders_count"], 0)
        self.assertEqual(result["revenue"], Decimal("0"))


class ProductReportTests(ReportsBaseTestCase):

    def test_top_products_by_quantity(self):
        result = ProductReport.top_products(self.yesterday, self.today)
        # Пиццы продано: 2+1+3 = 6 (без учёта отменённого o4); колы: 1
        result_map = {r["product__name"]: r for r in result}
        self.assertEqual(result_map["Маргарита"]["qty_sold"], 6)
        self.assertEqual(result_map["Кола"]["qty_sold"], 1)

    def test_top_products_revenue(self):
        result = ProductReport.top_products(self.yesterday, self.today)
        result_map = {r["product__name"]: r for r in result}
        # Пицца: 500*6 = 3000; кола: 100*1 = 100
        self.assertEqual(result_map["Маргарита"]["revenue"], Decimal("3000.00"))
        self.assertEqual(result_map["Кола"]["revenue"], Decimal("100.00"))

    def test_top_products_excludes_cancelled(self):
        """Позиции из отменённого заказа не должны учитываться."""
        result = ProductReport.top_products(self.yesterday, self.today)
        margarita = next(r for r in result if r["product__name"] == "Маргарита")
        # Если бы o4 учитывался, было бы 6 + 10 = 16
        self.assertEqual(margarita["qty_sold"], 6)

    def test_revenue_by_category(self):
        result = ProductReport.revenue_by_category(self.yesterday, self.today)
        cat_map = {r["product__category"]: r for r in result}
        self.assertEqual(cat_map["pizza"]["revenue"], Decimal("3000.00"))
        self.assertEqual(cat_map["drink"]["revenue"], Decimal("100.00"))


class ClientReportTests(ReportsBaseTestCase):

    def test_top_clients(self):
        result = ClientReport.top_clients(self.yesterday, self.today)
        self.assertEqual(len(result), 2)
        # Клиент A: o1(1100) + o2(500) = 1600; клиент B: 1500
        self.assertEqual(result[0]["full_name"], "Клиент A")
        self.assertEqual(result[0]["revenue"], Decimal("1600.00"))
        self.assertEqual(result[0]["orders_total"], 2)

    def test_cancellation_rate(self):
        result = ClientReport.cancellation_rate(self.yesterday, self.today)
        # Всего: 4, отменён: 1 → 25%
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["cancelled"], 1)
        self.assertEqual(result["rate"], 25.0)

    def test_cancellation_rate_no_orders(self):
        future = self.today + timedelta(days=10)
        result = ClientReport.cancellation_rate(future, future)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["rate"], 0)

    def test_inactive_clients(self):
        # Создаём клиента вообще без заказов
        ghost = Client.objects.create(full_name="Призрак", phone="+70000099999")
        inactive = list(ClientReport.inactive_clients(days=60))
        self.assertIn(ghost, inactive)

    def test_inactive_excludes_recent_buyers(self):
        # Клиент A заказывал сегодня → не должен быть в "спящих"
        inactive = list(ClientReport.inactive_clients(days=60))
        self.assertNotIn(self.client_a, inactive)
