from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, api

router = DefaultRouter()
router.register("clients", api.ClientViewSet)
router.register("orders", api.OrderViewSet)
router.register("products", api.ProductViewSet)
router.register("branches", api.BranchViewSet)

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("orders/", views.order_list, name="order_list"),
    path("orders/new/", views.order_create, name="order_create"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/edit/", views.order_edit, name="order_edit"),
    path("orders/<int:pk>/status/", views.order_change_status, name="order_change_status"),

    path("clients/", views.client_list, name="client_list"),
    path("clients/new/", views.client_create, name="client_create"),
    path("clients/<int:pk>/", views.client_detail, name="client_detail"),
    path("clients/<int:pk>/edit/", views.client_edit, name="client_edit"),

    path("api/", include(router.urls)),
]