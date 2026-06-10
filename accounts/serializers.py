import re

from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator
from rest_framework import serializers

User = get_user_model()

PASSWORD_COMPLEXITY = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>_\-]).+$'
)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    confirm_password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    class Meta:
        model = User
        fields = ["email", "username", "password", "confirm_password"]
        extra_kwargs = {
            "email": {"validators": []},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        EmailValidator()(value)
        return value

    def validate_username(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters.")
        if not re.match(r'^[a-zA-Z0-9_]+$', value):
            raise serializers.ValidationError("Username may only contain letters, numbers, and underscores.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_password(self, value):
        if not PASSWORD_COMPLEXITY.match(value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter, one lowercase letter, "
                "one digit, and one special character."
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError("Passwords do not match.")
        return attrs

    def create(self, validated_data):
        from .services import register_user
        return register_user(validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=128)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        from .services import authenticate_user, generate_tokens
        user = authenticate_user(attrs["email"], attrs["password"])
        tokens = generate_tokens(user)
        attrs["user"] = user
        attrs["tokens"] = tokens
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "avatar", "is_verified", "date_joined"]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8, max_length=128)

    def validate_new_password(self, value):
        if not PASSWORD_COMPLEXITY.match(value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter, one lowercase letter, "
                "one digit, and one special character."
            )
        return value
