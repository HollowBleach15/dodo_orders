from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView, TokenBlacklistView
from core.api import CustomTokenObtainPairView

urlpatterns = [
    path("admin/", admin.site.urls),

    # JWT endpoints
    path("api/auth/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/auth/logout/", TokenBlacklistView.as_view(), name="token_blacklist"),

    path("reports/", include("reports.urls")),
    path("", include("core.urls")),
]