from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status


class JWTAuthenticationTests(TestCase):
    """Получение, обновление, верификация и отзыв JWT-токенов."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="operator", password="testpass123", email="op@dodo.ru"
        )

    def setUp(self):
        self.api = APIClient()

    def test_obtain_token_success(self):
        resp = self.api.post(reverse("token_obtain_pair"),
                             {"username": "operator", "password": "testpass123"},
                             format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_obtain_token_wrong_password(self):
        resp = self.api.post(reverse("token_obtain_pair"),
                             {"username": "operator", "password": "wrong"},
                             format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_obtain_token_nonexistent_user(self):
        resp = self.api.post(reverse("token_obtain_pair"),
                             {"username": "ghost", "password": "any"},
                             format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_contains_custom_claims(self):
        """Проверка кастомных claims (username, is_staff, groups)."""
        from rest_framework_simplejwt.tokens import AccessToken
        resp = self.api.post(reverse("token_obtain_pair"),
                             {"username": "operator", "password": "testpass123"},
                             format="json")
        access = AccessToken(resp.data["access"])
        self.assertEqual(access["username"], "operator")
        self.assertFalse(access["is_staff"])
        self.assertEqual(access["groups"], [])

    def test_refresh_token_flow(self):
        obtain = self.api.post(reverse("token_obtain_pair"),
                               {"username": "operator", "password": "testpass123"},
                               format="json")
        refresh = obtain.data["refresh"]

        resp = self.api.post(reverse("token_refresh"),
                             {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)

    def test_verify_valid_token(self):
        obtain = self.api.post(reverse("token_obtain_pair"),
                               {"username": "operator", "password": "testpass123"},
                               format="json")
        resp = self.api.post(reverse("token_verify"),
                             {"token": obtain.data["access"]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_verify_invalid_token(self):
        resp = self.api.post(reverse("token_verify"),
                             {"token": "invalid.jwt.token"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blacklist_logout(self):
        obtain = self.api.post(reverse("token_obtain_pair"),
                               {"username": "operator", "password": "testpass123"},
                               format="json")
        refresh = obtain.data["refresh"]

        resp = self.api.post(reverse("token_blacklist"),
                             {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Повторное использование заблокированного refresh должно падать
        resp2 = self.api.post(reverse("token_refresh"),
                              {"refresh": refresh}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)
