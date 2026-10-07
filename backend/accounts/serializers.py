from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.models import User, UserRole
from accounts.otp import consume_verification_token
from accounts.phones import normalize_phone
from common.services import write_audit_event


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone", "phone_verified", "first_name", "last_name", "email", "role")
        read_only_fields = fields


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    purpose = serializers.ChoiceField(choices=("REGISTER", "LOGIN", "PASSWORD_RESET"))

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.CharField(max_length=12, trim_whitespace=True)
    purpose = serializers.ChoiceField(choices=("REGISTER", "LOGIN", "PASSWORD_RESET"))

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    verification_token = serializers.CharField(write_only=True, max_length=2048)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=10, max_length=128, trim_whitespace=False)
    role = serializers.ChoiceField(choices=(UserRole.CUSTOMER, UserRole.BTP_COMPANY), default=UserRole.CUSTOMER)
    terms_accepted = serializers.BooleanField(write_only=True)

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate_terms_accepted(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("Vous devez accepter les conditions d’utilisation.")
        return value

    def validate(self, attrs):
        if User.objects.filter(phone=attrs["phone"]).exists():
            raise serializers.ValidationError({"phone": "Un compte est déjà associé à ce numéro."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        phone_from_token = consume_verification_token(validated_data.pop("verification_token"), "REGISTER")
        phone = validated_data.pop("phone")
        if phone_from_token != phone:
            raise serializers.ValidationError({"verification_token": "Le numéro vérifié ne correspond pas."})
        password = validated_data.pop("password")
        validated_data.pop("terms_accepted")
        email = validated_data.pop("email", None) or None
        user = User.objects.create_user(phone=phone, password=password, email=email, **validated_data)
        user.phone_verified = True
        user.terms_accepted_at = timezone.now()
        user.save(update_fields=("phone_verified", "terms_accepted_at", "updated_at"))
        write_audit_event(event="account.registered", actor=user, object_type="user", object_id=user.pk)
        return user


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)


class OTPLoginSerializer(serializers.Serializer):
    verification_token = serializers.CharField(max_length=2048)


class PasswordResetConfirmSerializer(serializers.Serializer):
    verification_token = serializers.CharField(max_length=2048)
    password = serializers.CharField(write_only=True, min_length=10, max_length=128, trim_whitespace=False)

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    @transaction.atomic
    def save(self, **kwargs):
        phone = consume_verification_token(self.validated_data["verification_token"], "PASSWORD_RESET")
        user = User.objects.select_for_update().filter(phone=phone, is_active=True).first()
        if user is None:
            raise serializers.ValidationError({"verification_token": "Ce compte n’est plus disponible."})
        user.set_password(self.validated_data["password"])
        user.save(update_fields=("password", "updated_at"))
        for outstanding in OutstandingToken.objects.filter(user=user).iterator():
            BlacklistedToken.objects.get_or_create(token=outstanding)
        write_audit_event(event="account.password_reset", actor=user, object_type="user", object_id=user.pk)
        return user
