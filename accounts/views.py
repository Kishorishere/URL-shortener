import logging
import re
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model, login as django_login
from django.core.validators import EmailValidator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .exceptions import EmailNotVerifiedError, InvalidCredentialsError
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)

PASSWORD_COMPLEXITY = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>_\-]).+$'
)

User = get_user_model()
logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = services.generate_tokens(user)
        django_login(request, user)
        response = Response(
            UserProfileSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )
        services.set_auth_cookies(response, tokens)
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = serializer.validated_data["tokens"]
        django_login(request, user)
        response = Response(UserProfileSerializer(user).data)
        services.set_auth_cookies(response, tokens)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        from django.contrib.auth import logout as django_logout
        django_logout(request)
        response = redirect("login_page")
        services.clear_auth_cookies(response)
        return response


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_password(
            request.user,
            serializer.validated_data["old_password"],
            serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password changed successfully."})


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            token = RefreshToken(refresh_token)
            tokens = {
                "access": str(token.access_token),
                "refresh": str(token),
            }
            response = Response({"detail": "Token refreshed."})
            services.set_auth_cookies(response, tokens)
            return response
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


@require_http_methods(["GET", "POST"])
def verify_email_page(request):
    email = request.session.get("verification_email") or request.POST.get("email", "")
    if not email:
        return redirect("login_page")
    error = None
    if request.method == "POST":
        if "resend" in request.POST:
            request.session["verification_email"] = email
            _send_verification(request, email)
            return render(request, "accounts/verify_otp.html", {
                "error": "A new code has been sent to your email.",
                "email": email,
                "resend_url": reverse("verify_email_page"),
            })
        otp = request.POST.get("otp", "")
        stored = services.get_stored_otp(email)
        if stored and otp == stored:
            services.delete_otp(email)
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return redirect("login_page")
            user.is_verified = True
            user.save(update_fields=["is_verified"])
            django_login(request, user)
            tokens = services.generate_tokens(user)
            response = redirect(settings.LOGIN_REDIRECT_URL)
            services.set_auth_cookies(response, tokens)
            request.session.pop("verification_email", None)
            return response
        else:
            error = "Invalid or expired OTP. Please try again."
    return render(request, "accounts/verify_otp.html", {
        "error": error,
        "email": email,
        "resend_url": reverse("verify_email_page"),
    })


def root_redirect(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    return redirect("login_page")


def verify_email_link(request, token):
    email = services.unsign_email(token, timeout=settings.OTP_TIMEOUT)
    if not email:
        return render(request, "accounts/email_verified.html", {
            "success": False,
            "message": "This verification link is invalid or has expired.",
        })
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return render(request, "accounts/email_verified.html", {
            "success": False,
            "message": "User not found.",
        })
    user.is_verified = True
    user.save(update_fields=["is_verified"])
    services.delete_otp(email)
    request.session.pop("verification_email", None)
    django_login(request, user)
    tokens = services.generate_tokens(user)
    response = redirect(settings.LOGIN_REDIRECT_URL)
    services.set_auth_cookies(response, tokens)
    return response


@require_http_methods(["GET", "POST"])
def forgot_password_page(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    error = None
    sent = False
    if request.method == "POST":
        email = request.POST.get("email", "")
        try:
            user = User.objects.get(email=email)
            signed = services.sign_email(email)
            reset_url = request.build_absolute_uri(
                reverse("reset_password_page", kwargs={"token": signed})
            )
            services.send_password_reset_email(email, reset_url)
            sent = True
        except User.DoesNotExist:
            pass
        sent = True
    return render(request, "accounts/forgot_password.html", {
        "error": error,
        "sent": sent,
    })


@require_http_methods(["GET", "POST"])
def reset_password_page(request, token):
    error = None
    email = services.verify_password_reset_token(token)
    if request.method == "POST":
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")
        if password != confirm:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        else:
            user = services.reset_password_from_token(token, password)
            if user:
                return redirect("login_page")
            error = "This reset link is invalid or has expired."
    return render(request, "accounts/reset_password.html", {
        "error": error,
        "valid": email is not None,
        "token": token,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def google_login(request):
    redirect_uri = request.build_absolute_uri(reverse("accounts:google-callback"))
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return redirect(url)


@api_view(["GET"])
@permission_classes([AllowAny])
def google_callback(request):
    code = request.GET.get("code")
    error = request.GET.get("error")
    if error or not code:
        logger.warning("Google OAuth error: %s", error)
        return redirect(f"{settings.FRONTEND_URL}/login/")

    redirect_uri = request.build_absolute_uri(reverse("accounts:google-callback"))
    try:
        import requests as http_requests
        token_response = http_requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }, timeout=10)
        token_response.raise_for_status()
        token_data = token_response.json()
        id_token_str = token_data["id_token"]
    except Exception as e:
        logger.error("Google token exchange failed: %s", e)
        return redirect(f"{settings.FRONTEND_URL}/login/")

    try:
        claims = services.google_verify_id_token(id_token_str)
    except Exception:
        return redirect(f"{settings.FRONTEND_URL}/login/")

    user = services.google_find_or_create_user(claims)
    django_login(request, user)
    tokens = services.generate_tokens(user)
    response = redirect(settings.LOGIN_REDIRECT_URL)
    services.set_auth_cookies(response, tokens)
    return response


@require_http_methods(["GET", "POST"])
def login_page(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    error = None
    verify_email = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        if not email:
            error = "Email is required."
        elif not password:
            error = "Password is required."
        if not error:
            try:
                user = services.authenticate_user(email, password)
                django_login(request, user)
                tokens = services.generate_tokens(user)
                response = redirect(settings.LOGIN_REDIRECT_URL)
                services.set_auth_cookies(response, tokens)
                return response
            except EmailNotVerifiedError:
                error = "Please verify your email address first."
                verify_email = email
            except Exception as e:
                error = str(e) or "Invalid email or password."
    return render(request, "accounts/login.html", {
        "error": error,
        "verify_email": verify_email,
        "google_login_url": reverse("accounts:google-login"),
    })


def _send_verification(request, email: str):
    """Generate OTP + signed link and email them to user."""
    otp = services.generate_otp()
    services.store_otp(email, otp)
    signed_email = services.sign_email(email, timeout=settings.OTP_TIMEOUT)
    verification_url = request.build_absolute_uri(
        reverse("verify_email_link", kwargs={"token": signed_email})
    )
    services.send_otp_email(email, otp, verification_url)
    request.session["verification_email"] = email


@require_http_methods(["GET", "POST"])
def register_page(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        username = request.POST.get("username", "").strip()

        if not email:
            error = "Email is required."
        elif not password:
            error = "Password is required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif len(password) > 128:
            error = "Password must be at most 128 characters."
        elif not PASSWORD_COMPLEXITY.match(password):
            error = "Password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif not username:
            error = "Name is required."
        elif len(username) < 3:
            error = "Name must be at least 3 characters."
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            error = "Name may only contain letters, numbers, and underscores."

        if not error:
            try:
                user = services.register_user({
                    "email": email,
                    "password": password,
                    "confirm_password": confirm_password,
                    "username": username or email.split("@")[0],
                })
                _send_verification(request, email)
                return redirect("verify_email_page")
            except Exception as e:
                error = str(e) or "Registration failed."
    return render(request, "accounts/register.html", {
        "error": error,
        "google_login_url": reverse("accounts:google-login"),
    })
