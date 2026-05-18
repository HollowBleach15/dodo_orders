from django.db import transaction
from .models import Order, OrderItem, Product
from decimal import Decimal


class OrderService:
    ALLOWED_TRANSITIONS = {
        "new": {"in_work", "cancelled"},
        "in_work": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    @classmethod
    @transaction.atomic
    def save_order_with_items(cls, order: Order, items_data: list) -> Order:
        client_pk = getattr(order, "client_id", None)
        if order.discount_percent == Decimal("0") and client_pk:
            from .models import Client
            client = Client.objects.get(pk=client_pk)
            order.discount_percent = client.default_discount

        order.save()

        OrderItem.objects.filter(order=order).delete()
        for row in items_data:
            product = Product.objects.get(pk=row["product_id"])
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=row["quantity"],
                price=product.price,
            )
        order.recalc_total()
        order.save(update_fields=["total"])
        return order

    @classmethod
    def change_status(cls, order: Order, new_status: str) -> Order:
        if new_status not in cls.ALLOWED_TRANSITIONS.get(order.status, set()):
            raise ValueError(
                f"Переход {order.status} → {new_status} не разрешён"
            )
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        return order