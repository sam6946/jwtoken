from django.urls import path

from accounts.views import (
    CookieTokenRefreshAPIView,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
    OTPLoginAPIView,
    OTPRequestAPIView,
    OTPVerifyAPIView,
    PasswordResetConfirmAPIView,
    RegisterAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("otp/request/", OTPRequestAPIView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyAPIView.as_view(), name="otp-verify"),
    path("otp/login/", OTPLoginAPIView.as_view(), name="otp-login"),
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("password-reset/confirm/", PasswordResetConfirmAPIView.as_view(), name="password-reset-confirm"),
    path("token/refresh/", CookieTokenRefreshAPIView.as_view(), name="token-refresh"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("me/", MeAPIView.as_view(), name="me"),
]
