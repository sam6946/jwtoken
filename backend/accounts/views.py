import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.otp import consume_verification_token, request_otp, verify_otp
from accounts.serializers import (
    LoginSerializer,
    OTPLoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    UserSerializer,
)
from common.cookies import delete_refresh_cookie, set_refresh_cookie
from common.services import write_audit_event

logger = logging.getLogger("kemta")


def _auth_response(user: User, request) -> Response:
    refresh = RefreshToken.for_user(user)
    user.last_login = timezone.now()
    user.save(update_fields=("last_login",))
    payload = {"access": str(refresh.access_token), "user": UserSerializer(user).data}
    if settings.REFRESH_TOKEN_IN_BODY:
        payload["refresh"] = str(refresh)
    response = Response(payload)
    set_refresh_cookie(response, str(refresh), request)
    return response


class OTPRequestAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = request_otp(serializer.validated_data["phone"], serializer.validated_data["purpose"])
        payload = {"detail": result.detail, "expires_in": result.expires_in}
        if settings.DEBUG and result.debug_code:
            payload["debug_code"] = result.debug_code
        return Response(payload, status=status.HTTP_200_OK)


class OTPVerifyAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        token = verify_otp(phone, serializer.validated_data["code"], serializer.validated_data["purpose"])
        return Response({"verification_token": token, "phone": phone}, status=status.HTTP_200_OK)


class RegisterAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return _auth_response(user, request)


class LoginAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            phone=serializer.validated_data["phone"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            raise AuthenticationFailed("Numéro ou mot de passe incorrect.")
        return _auth_response(user, request)


class OTPLoginAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = OTPLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = consume_verification_token(serializer.validated_data["verification_token"], "LOGIN")
        user = User.objects.filter(phone=phone, is_active=True).first()
        if user is None:
            raise AuthenticationFailed("Ce compte n’est pas disponible.")
        write_audit_event(event="account.otp_login", actor=user, object_type="user", object_id=user.pk, request_id=getattr(request, "request_id", ""))
        return _auth_response(user, request)


class PasswordResetConfirmAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Le mot de passe a été modifié."}, status=status.HTTP_200_OK)


class CookieTokenRefreshAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = ()

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw_refresh and settings.REFRESH_TOKEN_IN_BODY:
            # Repli pour les contextes où le navigateur bloque les cookies tiers (iframe d'aperçu).
            candidate = request.data.get("refresh") if isinstance(request.data, dict) else None
            raw_refresh = candidate if isinstance(candidate, str) and candidate else None
        if not raw_refresh:
            raise AuthenticationFailed("Session expirée. Connectez-vous à nouveau.")
        try:
            refresh = RefreshToken(raw_refresh)
            user_id = refresh.get(api_settings.USER_ID_CLAIM)
            user = User.objects.filter(pk=user_id, is_active=True).first()
            if user is None:
                raise AuthenticationFailed("Compte indisponible.")
            access = str(refresh.access_token)
            if api_settings.ROTATE_REFRESH_TOKENS:
                if api_settings.BLACKLIST_AFTER_ROTATION:
                    refresh.blacklist()
                new_refresh = RefreshToken.for_user(user)
                response = Response({"access": str(new_refresh.access_token)})
                set_refresh_cookie(response, str(new_refresh), request)
                return response
            return Response({"access": access})
        except TokenError:
            response = Response({"detail": "Session expirée. Connectez-vous à nouveau."}, status=status.HTTP_401_UNAUTHORIZED)
            delete_refresh_cookie(response)
            return response


class LogoutAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = ()

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw_refresh and settings.REFRESH_TOKEN_IN_BODY and isinstance(request.data, dict):
            candidate = request.data.get("refresh")
            raw_refresh = candidate if isinstance(candidate, str) and candidate else None
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                logger.info("Logout received an expired refresh token")
        write_audit_event(event="account.logout", actor=request.user, object_type="user", object_id=request.user.pk, request_id=getattr(request, "request_id", ""))
        response = Response({"detail": "Vous êtes déconnecté."}, status=status.HTTP_200_OK)
        delete_refresh_cookie(response)
        return response


class MeAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = ()

    def get(self, request):
        return Response(UserSerializer(request.user).data)
