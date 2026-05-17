from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Client, Branch, Product, Order


class APIAuthorizationTests(TestCase):
    """Проверка, что API закрыт для неаутентифицированных пользователей."""

    def test_orders_list_requires_auth(self):
        api = APIClient()
        resp = api.get("/api/orders/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_clients_list_requires_auth(self):
        api = APIClient()
        resp = api.get("/api/clients/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_bearer_token_rejected(self):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
        resp = api.get("/api/orders/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class APIBaseTestCase(TestCase):
    """Базовый класс с настроенной JWT-аутентификацией."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="operator", password="pass123", email="op@dodo.ru"
        )
        cls.manager_group, _ = Group.objects.get_or_create(name="managers")
        cls.manager = User.objects.create_user(
            username="manager", password="pass123", email="mgr@dodo.ru"
        )
        cls.manager.groups.add(cls.manager_group)

        cls.client_obj = Client.objects.create(
            full_name="Анна Сидорова", phone="+79991112233", email="anna@example.com"
        )
        cls.branch = Branch.objects.create(name="Тверская", address="Москва")
        cls.pizza = Product.objects.create(
            name="Маргарита", category="pizza", price=Decimal("500.00")
        )
        cls.drink = Product.objects.create(
            name="Кола", category="drink", price=Decimal("100.00")
        )

    def setUp(self):
        self.api = APIClient()

    def authenticate(self, username="operator", password="pass123"):
        resp = self.api.post(reverse("token_obtain_pair"),
                             {"username": username, "password": password},
                             format="json")
        self.assertEqual(resp.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")


class ClientAPITests(APIBaseTestCase):

    def test_list_clients_authenticated(self):
        self.authenticate()
        resp = self.api.get("/api/clients/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_create_client(self):
        self.authenticate()
        resp = self.api.post("/api/clients/", {
            "full_name": "Иван Петров",
            "phone": "+79994445566",
            "email": "ivan@example.com",
            "address": "ул. Ленина, 1",
            "is_active": True,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Client.objects.count(), 2)

    def test_search_clients_by_phone(self):
        self.authenticate()
        resp = self.api.get("/api/clients/?search=111")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_update_client(self):
        self.authenticate()
        resp = self.api.patch(f"/api/clients/{self.client_obj.pk}/",
                              {"address": "Новый адрес"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.address, "Новый адрес")

    def test_delete_client(self):
        self.authenticate()
        resp = self.api.delete(f"/api/clients/{self.client_obj.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class OrderAPITests(APIBaseTestCase):

    def test_create_order_with_items(self):
        self.authenticate()
        resp = self.api.post("/api/orders/", {
            "client": self.client_obj.pk,
            "branch": self.branch.pk,
            "status": "new",
            "order_type": "delivery",
            "discount_percent": "0",
            "items": [
                {"product": self.pizza.pk, "quantity": 2},
                {"product": self.drink.pk, "quantity": 1},
            ],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # 500*2 + 100*1 = 1100
        self.assertEqual(Decimal(resp.data["total"]), Decimal("1100.00"))

    def test_create_order_with_discount(self):
        self.authenticate()
        resp = self.api.post("/api/orders/", {
            "client": self.client_obj.pk,
            "branch": self.branch.pk,
            "discount_percent": "15",
            "items": [{"product": self.pizza.pk, "quantity": 2}],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # 500*2 = 1000, -15% = 850
        self.assertEqual(Decimal(resp.data["total"]), Decimal("850.00"))

    def test_filter_orders_by_status(self):
        self.authenticate()
        Order.objects.create(client=self.client_obj, branch=self.branch, status="new")
        Order.objects.create(client=self.client_obj, branch=self.branch, status="done")

        resp = self.api.get("/api/orders/?status=new")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_change_status_action_success(self):
        self.authenticate()
        order = Order.objects.create(client=self.client_obj, branch=self.branch, status="new")
        resp = self.api.post(f"/api/orders/{order.pk}/change_status/",
                             {"status": "in_work"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "in_work")

    def test_change_status_forbidden_transition(self):
        self.authenticate()
        order = Order.objects.create(client=self.client_obj, branch=self.branch, status="done")
        resp = self.api.post(f"/api/orders/{order.pk}/change_status/",
                             {"status": "new"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data["ok"])


class ProductAPIPermissionTests(APIBaseTestCase):
    """Проверка кастомного permission IsManagerOrReadOnly."""

    def test_operator_can_read_products(self):
        self.authenticate("operator", "pass123")
        resp = self.api.get("/api/products/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_operator_cannot_create_product(self):
        self.authenticate("operator", "pass123")
        resp = self.api.post("/api/products/", {
            "name": "Новая", "category": "pizza", "price": "999.00", "is_active": True
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_create_product(self):
        self.authenticate("manager", "pass123")
        resp = self.api.post("/api/products/", {
            "name": "Новая", "category": "pizza", "price": "999.00", "is_active": True
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
