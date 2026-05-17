from decimal import Decimal
from django.test import TestCase

from core.models import Client, Branch, Product, Order, OrderItem
from core.services import OrderService


class OrderServiceStatusTransitionTests(TestCase):
    """Проверка матрицы допустимых переходов статусов."""

    @classmethod
    def setUpTestData(cls):
        cls.client_obj = Client.objects.create(full_name="Иван Иванов", phone="+79990000001")
        cls.branch = Branch.objects.create(name="Тверская", address="Москва, Тверская, 1")
        cls.product = Product.objects.create(name="Маргарита", category="pizza", price=Decimal("500.00"))

    def _make_order(self, status="new"):
        order = Order.objects.create(client=self.client_obj, branch=self.branch, status=status)
        OrderItem.objects.create(order=order, product=self.product, quantity=1, price=Decimal("500.00"))
        order.recalc_total()
        order.save()
        return order

    def test_new_to_in_work_allowed(self):
        order = self._make_order("new")
        OrderService.change_status(order, "in_work")
        order.refresh_from_db()
        self.assertEqual(order.status, "in_work")

    def test_new_to_cancelled_allowed(self):
        order = self._make_order("new")
        OrderService.change_status(order, "cancelled")
        order.refresh_from_db()
        self.assertEqual(order.status, "cancelled")

    def test_in_work_to_done_allowed(self):
        order = self._make_order("in_work")
        OrderService.change_status(order, "done")
        self.assertEqual(order.status, "done")

    def test_done_to_anything_forbidden(self):
        order = self._make_order("done")
        for target in ("new", "in_work", "cancelled"):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    OrderService.change_status(order, target)

    def test_cancelled_to_anything_forbidden(self):
        order = self._make_order("cancelled")
        with self.assertRaises(ValueError):
            OrderService.change_status(order, "in_work")

    def test_new_to_done_skipping_forbidden(self):
        """Прямой переход new→done запрещён — заказ должен пройти in_work."""
        order = self._make_order("new")
        with self.assertRaises(ValueError):
            OrderService.change_status(order, "done")

    def test_unknown_status_forbidden(self):
        order = self._make_order("new")
        with self.assertRaises(ValueError):
            OrderService.change_status(order, "unknown_status")


class OrderServiceTotalCalculationTests(TestCase):
    """Проверка расчёта итоговой суммы с учётом скидки."""

    @classmethod
    def setUpTestData(cls):
        cls.client_obj = Client.objects.create(full_name="Пётр Петров", phone="+79990000002")
        cls.branch = Branch.objects.create(name="Арбат", address="Москва, Арбат, 1")
        cls.pizza = Product.objects.create(name="Пепперони", category="pizza", price=Decimal("700.00"))
        cls.drink = Product.objects.create(name="Кола 0.5", category="drink", price=Decimal("120.00"))

    def test_total_without_discount(self):
        order = Order(client=self.client_obj, branch=self.branch, discount_percent=Decimal("0"))
        OrderService.save_order_with_items(order, [
            {"product_id": self.pizza.pk, "quantity": 2},
            {"product_id": self.drink.pk, "quantity": 1},
        ])
        # 700*2 + 120*1 = 1520
        self.assertEqual(order.total, Decimal("1520.00"))

    def test_total_with_10_percent_discount(self):
        order = Order(client=self.client_obj, branch=self.branch, discount_percent=Decimal("10"))
        OrderService.save_order_with_items(order, [
            {"product_id": self.pizza.pk, "quantity": 1},
            {"product_id": self.drink.pk, "quantity": 2},
        ])
        # (700 + 240) * 0.9 = 846.00
        self.assertEqual(order.total, Decimal("846.00"))

    def test_total_with_100_percent_discount(self):
        order = Order(client=self.client_obj, branch=self.branch, discount_percent=Decimal("100"))
        OrderService.save_order_with_items(order, [
            {"product_id": self.pizza.pk, "quantity": 1},
        ])
        self.assertEqual(order.total, Decimal("0.00"))

    def test_rounding_to_two_decimals(self):
        product = Product.objects.create(name="Кофе", category="drink", price=Decimal("99.99"))
        order = Order(client=self.client_obj, branch=self.branch, discount_percent=Decimal("33"))
        OrderService.save_order_with_items(order, [
            {"product_id": product.pk, "quantity": 3},
        ])
        # 99.99 * 3 = 299.97; *0.67 = 200.9799 → 200.98
        self.assertEqual(order.total, Decimal("200.98"))

    def test_items_count_matches(self):
        order = Order(client=self.client_obj, branch=self.branch)
        OrderService.save_order_with_items(order, [
            {"product_id": self.pizza.pk, "quantity": 1},
            {"product_id": self.drink.pk, "quantity": 1},
        ])
        self.assertEqual(order.items.count(), 2)

    def test_resaving_replaces_items(self):
        """При повторном сохранении старые позиции должны быть заменены."""
        order = Order(client=self.client_obj, branch=self.branch)
        OrderService.save_order_with_items(order, [
            {"product_id": self.pizza.pk, "quantity": 1},
        ])
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total, Decimal("700.00"))

        OrderService.save_order_with_items(order, [
            {"product_id": self.drink.pk, "quantity": 3},
        ])
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total, Decimal("360.00"))

    def test_price_snapshot_in_item(self):
        """Цена в OrderItem должна сохраняться на момент заказа (не меняться при изменении товара)."""
        order = Order(client=self.client_obj, branch=self.branch)
        OrderService.save_order_with_items(order, [
            {"product_id": self.pizza.pk, "quantity": 1},
        ])
        first_item = order.items.first()
        assert first_item is not None
        item_price = first_item.price

        # Меняем цену товара
        self.pizza.price = Decimal("1000.00")
        self.pizza.save()

        order.refresh_from_db()
        refetched = order.items.first()
        assert refetched is not None
        self.assertEqual(refetched.price, item_price)


class OrderServiceTransactionTests(TestCase):
    """Проверка транзакционной целостности."""

    @classmethod
    def setUpTestData(cls):
        cls.client_obj = Client.objects.create(full_name="Тест", phone="+79990000003")
        cls.branch = Branch.objects.create(name="Тест", address="Тест")
        cls.product = Product.objects.create(name="Тест", category="pizza", price=Decimal("100.00"))

    def test_rollback_on_invalid_product(self):
        """При ошибке (несуществующий товар) старые позиции должны сохраниться."""
        order = Order(client=self.client_obj, branch=self.branch)
        OrderService.save_order_with_items(order, [
            {"product_id": self.product.pk, "quantity": 1},
        ])
        original_total = order.total
        original_count = order.items.count()

        with self.assertRaises(Product.DoesNotExist):
            OrderService.save_order_with_items(order, [
                {"product_id": 99999, "quantity": 1},  # несуществующий
            ])

        order.refresh_from_db()
        self.assertEqual(order.items.count(), original_count)
        self.assertEqual(order.total, original_total)
