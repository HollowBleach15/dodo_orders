from django.contrib import admin
from .models import Client, Order, OrderItem, Product, Branch


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "branch", "status", "total", "created_at")
    list_filter = ("status", "branch", "order_type")
    search_fields = ("client__full_name", "client__phone")
    inlines = [OrderItemInline]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "is_active", "created_at")
    search_fields = ("full_name", "phone", "email")
    list_filter = ("is_active",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address")