from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import (
    LoginView, MeView, ChangePasswordView, UserViewSet, RoleListView, PsychologistListView,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("roles/", RoleListView.as_view(), name="role-list"),
    path("psychologists/", PsychologistListView.as_view(), name="psychologists"),
    path("", include(router.urls)),
]
