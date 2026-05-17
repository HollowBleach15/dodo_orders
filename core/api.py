from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import AbstractUser

from .models import Client, Order, Product, Branch
from .serializers import (
    ClientSerializer, OrderSerializer, ProductSerializer, BranchSerializer,
)
from .services import OrderService


class IsManagerOrReadOnly(permissions.BasePermission):
    """Менеджеры/админы — полный доступ, остальные — только чтение."""

    def has_permission(self, request, view):
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return bool(user and user.is_authenticated)
        if not isinstance(user, AbstractUser):
            return False
        return bool(
            user.is_staff
            or user.groups.filter(name="managers").exists()
        )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Расширенный JWT: в токен зашиваем имя пользователя и роль."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        if isinstance(user, AbstractUser):
            token["username"] = user.username
            token["is_staff"] = user.is_staff
            token["groups"] = list(user.groups.values_list("name", flat=True))
        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_active"]
    search_fields = ["full_name", "phone", "email"]


class OrderViewSet(viewsets.ModelViewSet):
    queryset = (
        Order.objects.select_related("client", "branch")
        .prefetch_related("items__product")
    )
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "branch", "client", "order_type"]

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        """POST /api/orders/{id}/change_status/ {"status": "in_work"}"""
        order = self.get_object()
        try:
            OrderService.change_status(order, request.data.get("status"))
        except ValueError as e:
            return Response({"ok": False, "error": str(e)}, status=400)

        try:
            from .tasks import notify_client_about_status
            notify_client_about_status.delay(order.pk)  # type: ignore[attr-defined]
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Не удалось поставить задачу уведомления: %s", exc
            )

        return Response({"ok": True, "status": order.status})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsManagerOrReadOnly]
    filterset_fields = ["category", "is_active"]


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsManagerOrReadOnly]
