from django.urls import path
from . import views
from .views import order_export_excel

urlpatterns = [
    path("", views.index, name="reports_index"),
    path("revenue/", views.revenue, name="reports_revenue"),
    path("products/", views.products, name="reports_products"),
    path("clients/", views.clients, name="reports_clients"),
    path("revenue/export.xlsx", views.export_revenue_xlsx, name="reports_revenue_xlsx"),
    path("order/<int:pk>/export/excel/", order_export_excel, name="order_export_excel"),
]