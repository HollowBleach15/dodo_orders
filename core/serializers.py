# pyright: reportIncompatibleVariableOverride=false
from rest_framework import serializers
from .models import Client, Order, OrderItem, Product, Branch


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = "__all__"


class ClientSerializer(serializers.ModelSerializer):
    orders_count = serializers.IntegerField(read_only=True)
    class Meta:
        model = Client
        fields = ["id", "full_name", "phone", "email", "address", "client_type", "is_active", "created_at", "orders_count"]


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "quantity", "price", "line_total"]
        read_only_fields = ["price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    client_name = serializers.CharField(source="client.full_name", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "client", "client_name", "branch", "status", "order_type", "discount_percent", "total", "comment", "created_at", "updated_at", "items"]
        read_only_fields = ["total", "created_at", "updated_at"]

    def create(self, validated_data):
        from .services import OrderService
        items = validated_data.pop("items")
        order = Order(**validated_data)
        items_data = [{"product_id": i["product"].id, "quantity": i["quantity"]} for i in items]
        return OrderService.save_order_with_items(order, items_data)

    def update(self, instance, validated_data):
        from .services import OrderService
        items = validated_data.pop("items", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if items is not None:
            items_data = [{"product_id": i["product"].id, "quantity": i["quantity"]} for i in items]
            return OrderService.save_order_with_items(instance, items_data)
        instance.save()
        return instance