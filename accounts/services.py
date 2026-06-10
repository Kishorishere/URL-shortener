import logging
import random
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework_simplejwt.tokens import RefreshToken

from .exceptions import EmailNotVerifiedError, InvalidCredentialsError, UserAlreadyExistsError

logger = logging.getLogger(__name__)
User = get_user_model()


def register_user(validated_data: dict):
    validated_data.pop("confirm_password", None)
    email = validated_data.pop("email")
    password = validated_data.pop("password")
    if User.objects.filter(email=email).exists():
        raise UserAlreadyExistsError()
    user = User.objects.create_user(email=email, password=password, **validated_data)
    post_auth_hook(user)
    return user


def authenticate_user(email: str, password: str):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise InvalidCredentialsError()
    if not check_password(password, user.password):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InvalidCredentialsError()
    if not user.is_verified and not user.google_id:
        raise EmailNotVerifiedError()
    return user


def generate_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def change_password(user, old_password: str, new_password: str):
    if not check_password(old_password, user.password):
        raise InvalidCredentialsError()
    user.set_password(new_password)
    user.save(update_fields=["password"])


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def store_otp(email: str, otp: str):
    cache.set(f"otp_{email}", otp, settings.OTP_TIMEOUT)


def get_stored_otp(email: str) -> str | None:
    return cache.get(f"otp_{email}")


def delete_otp(email: str):
    cache.delete(f"otp_{email}")


def send_otp_email(email: str, otp: str, verification_url: str):
    subject = "Verify your email — URL Shortener"
    html_message = render_to_string("accounts/emails/verify_otp.html", {
        "otp": otp,
        "verification_url": verification_url,
    })
    plain_message = strip_tags(html_message)
    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [email], html_message=html_message)


def send_password_reset_email(email: str, reset_url: str):
    subject = "Reset your password — URL Shortener"
    html_message = render_to_string("accounts/emails/password_reset.html", {
        "reset_url": reset_url,
    })
    plain_message = strip_tags(html_message)
    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [email], html_message=html_message)


def sign_email(email: str, timeout: int | None = None) -> str:
    signer = TimestampSigner()
    return signer.sign(email)


def unsign_email(signed_email: str, timeout: int | None = None) -> str | None:
    signer = TimestampSigner()
    try:
        return signer.unsign(signed_email, max_age=timeout or settings.PASSWORD_RESET_TIMEOUT)
    except (BadSignature, SignatureExpired):
        return None


def verify_password_reset_token(token: str) -> str | None:
    return unsign_email(token)


def reset_password_from_token(token: str, new_password: str) -> User | None:
    email = unsign_email(token)
    if not email:
        return None
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return None
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


def post_auth_hook(user):
    pass


def google_verify_id_token(id_token_str: str) -> dict:
    """Verify Google's ID token and return the decoded claims."""
    try:
        info = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
        return info
    except ValueError as e:
        logger.warning("Google token verification failed: %s", e)
        raise InvalidCredentialsError("Invalid Google token.")


@transaction.atomic
def google_find_or_create_user(claims: dict) -> User:
    """Find user by google_id or email, or create a new one."""
    google_id = claims.get("sub")
    email = claims.get("email", "")
    name = claims.get("name", "")

    user = None
    if google_id:
        user = User.objects.filter(google_id=google_id).first()
    if not user and email:
        user = User.objects.filter(email=email).first()
        if user and google_id and not user.google_id:
            user.google_id = google_id
            user.is_verified = True
            if name and not user.username:
                user.username = name
            user.save(update_fields=["google_id", "is_verified", "username"])

    if not user:
        username = name or email.split("@")[0] or f"user_{secrets.token_hex(4)}"
        random_password = secrets.token_urlsafe(32)
        user = User.objects.create_user(
            email=email,
            password=random_password,
            username=username,
            google_id=google_id,
            is_verified=True,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        post_auth_hook(user)

    return user


def set_auth_cookies(response, tokens):
    """Set JWT cookies on the response (shared helper for all login flows)."""
    response.set_cookie(
        key="access_token",
        value=tokens["access"],
        httponly=True,
        samesite="Lax",
        secure=getattr(settings, "SECURE_COOKIE", False),
        max_age=900,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh"],
        httponly=True,
        samesite="Lax",
        secure=getattr(settings, "SECURE_COOKIE", False),
        max_age=604800,
        path="/",
    )


def clear_auth_cookies(response):
    """Clear JWT cookies on the response (shared helper)."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
