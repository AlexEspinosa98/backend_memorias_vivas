from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import LoginView, MeView, RegisterView, UserDetailView

urlpatterns = [
    path("registro/", RegisterView.as_view(), name="registro"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("verify/", TokenVerifyView.as_view(), name="verify"),
    path("yo/", MeView.as_view(), name="yo"),
    path("usuarios/<int:pk>/", UserDetailView.as_view(), name="usuario-detalle"),
]
