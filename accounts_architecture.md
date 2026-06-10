# `accounts` App — Architecture & Responsibility Map

## Overview

The `accounts` app owns everything related to identity in this project — user creation,
authentication, token management, and profile data. It has zero dependency on `shortener`
or any other app. Any future Django project can drop this app in and wire it up.

Auth strategy: **JWT via `djangorestframework-simplejwt`**. No session-based auth.
The API is stateless — every request carries a token, the server verifies it, done.

---

## File Structure

```
accounts/
├── __init__.py
├── apps.py
├── admin.py
├── models.py
├── serializers.py
├── views.py
├── urls.py
├── services.py
├── permissions.py
├── signals.py
├── managers.py
├── exceptions.py
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_views.py
│   └── test_services.py
└── migrations/
    └── __init__.py
```

---

## File-by-File Breakdown

---

### `models.py`

**What it does:** Defines the `User` database table by extending Django's built-in
`AbstractUser`. This is the single most important decision in the accounts app —
make it early, make it right, never change it after the first migration.

**Why extend `AbstractUser` instead of building from scratch?**
Django's `AbstractUser` gives you password hashing, permission system, `is_active`,
`is_staff`, `date_joined`, `last_login` — all battle-tested. You're adding fields
on top, not reinventing the wheel.

**What we add on top:**
- `phone_number` — optional, for future OTP/SMS auth
- `avatar` — profile picture URL (stored in S3 later, just a URLField for now)
- `is_verified` — email verification flag, default `False`
- `updated_at` — auto-updated timestamp

**Key rule:** After defining this model, you MUST set `AUTH_USER_MODEL = 'accounts.User'`
in `base.py` BEFORE running any migration. Django's ORM references this setting
everywhere internally. Changing it after migrations exist is painful.

```python
# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.URLField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'       # login with email, not username
    REQUIRED_FIELDS = ['username'] # still required for createsuperuser

    objects = UserManager()

    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email
```

---

### `managers.py`

**What it does:** Overrides Django's default `UserManager` to handle the fact that
we use `email` as the login field, not `username`. Without this, `createsuperuser`
and `create_user` break because they assume `username` is the identifier.

Django's `Manager` is the ORM layer — `User.objects` is an instance of the Manager.
You can also put complex query logic here to keep views and services clean.

```python
# managers.py
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # hashes the password
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(email, password, **extra_fields)
```

---

### `serializers.py`

**What it does:** Handles data validation for incoming requests and data shaping
for outgoing responses. In DRF, a serializer is your DTO layer — it sits between
raw HTTP data and your Python objects.

**Serializers we need:**

`RegisterSerializer` — validates registration input, creates the user.
`LoginSerializer` — validates email + password, returns tokens.
`UserProfileSerializer` — read-only representation of the authenticated user.
`ChangePasswordSerializer` — validates old password + new password rules.

**Key concept — `validate_<field>`:** DRF calls field-level validators automatically.
If you define `validate_email`, DRF runs it whenever email is in the payload.

**Key concept — `validate`:** The global validator. Runs after all field validators.
Use it for cross-field validation (e.g. password === confirm_password).

```python
# serializers.py (structure only — write the logic yourself)
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()  # always reference User this way, never import directly


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'confirm_password']

    def validate(self, attrs):
        # cross-field validation: do passwords match?
        ...

    def create(self, validated_data):
        # call service layer here, not raw ORM
        ...


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'avatar', 'is_verified', 'date_joined']
        read_only_fields = fields  # profile is read-only via this serializer
```

---

### `services.py`

**What it does:** Contains all business logic for the accounts domain. Views call
services. Services call the ORM. This keeps views thin (HTTP only) and logic
testable without spinning up a request/response cycle.

**This file does not exist in Django by default — you create it.**

**Why a service layer?**
Without it, business logic bleeds into views. Views become fat, untestable, and
impossible to reuse. A service function is a plain Python function — you can call
it from a view, a management command, a signal, a test, anywhere.

**Services we need:**

`register_user(data)` — validates uniqueness, creates user, fires signal.
`authenticate_user(email, password)` — checks credentials, returns user or raises.
`generate_tokens(user)` — wraps simplejwt token generation.
`change_password(user, old_password, new_password)` — validates old, sets new.

```python
# services.py (structure)
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from .exceptions import InvalidCredentialsError

User = get_user_model()


def register_user(validated_data: dict) -> User:
    ...

def authenticate_user(email: str, password: str) -> User:
    ...

def generate_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def change_password(user: User, old_password: str, new_password: str) -> None:
    ...
```

---

### `views.py`

**What it does:** Handles HTTP concerns only. Parse the request, call the serializer,
call the service, return the response. Nothing more.

**Views we need:**

`RegisterView` — POST `/auth/register/`
`LoginView` — POST `/auth/login/` → returns JWT access + refresh tokens
`LogoutView` — POST `/auth/logout/` → blacklists the refresh token
`ProfileView` — GET `/auth/profile/` → returns authenticated user's data
`ChangePasswordView` — POST `/auth/change-password/`
`TokenRefreshView` — POST `/auth/token/refresh/` → simplejwt handles this

**Class-based vs function-based:**
Use `APIView` from DRF for explicit control. For standard CRUD, use DRF's
`generics.CreateAPIView`, `generics.RetrieveUpdateAPIView` etc. — they reduce
boilerplate significantly. Mix both in the same project to demonstrate you know both.

```python
# views.py (structure)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import RegisterSerializer, UserProfileSerializer
from . import services


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.register_user(serializer.validated_data)
        tokens = services.generate_tokens(user)
        return Response(tokens, status=status.HTTP_201_CREATED)


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user  # the authenticated user from the JWT
```

---

### `urls.py`

**What it does:** Maps URL patterns to views within the accounts app. This file
is then included in the root `config/urls.py` under a prefix like `/auth/`.

Keeping URL definitions inside the app (not the root urls.py) is the correct pattern
— it keeps the app self-contained and portable.

```python
# urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'accounts'  # namespace — lets you do reverse('accounts:login') anywhere

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
```

---

### `permissions.py`

**What it does:** Custom DRF permission classes. DRF's built-in permissions cover
`IsAuthenticated`, `IsAdminUser`, `AllowAny`. When you need something more specific
to your domain, you write it here.

**Custom permissions we'll add:**

`IsVerifiedUser` — only allows access if `user.is_verified` is `True`. Useful for
protecting certain endpoints until email verification is complete.

```python
# permissions.py
from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    message = 'Email verification required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_verified
        )
```

---

### `signals.py`

**What it does:** Django signals are a pub/sub system built into the framework.
When something happens (a model is saved, deleted, a user logs in), Django fires
a signal. You can connect handlers to those signals to run side effects without
coupling the triggering code to the side effect code.

**Signals we use:**

`post_save` on `User` — fires after a user is created. We use it to send a
welcome email (or log the event). The view doesn't know or care about this.

```python
# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    if created:
        # send welcome email, create default profile, log event, etc.
        print(f'New user registered: {instance.email}')
```

**Important:** Signals must be connected to run. Do this in `apps.py`:

```python
# apps.py
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        import accounts.signals  # this line connects the signal handlers
```

---

### `exceptions.py`

**What it does:** Custom exception classes for the accounts domain. Raising a
named exception (`InvalidCredentialsError`) is cleaner than raising a generic
`ValueError` or returning an error dict from a service function.

DRF has an exception handler that converts exceptions to HTTP responses automatically.
You can register a custom handler in settings to catch your own exception types.

```python
# exceptions.py
from rest_framework.exceptions import APIException
from rest_framework import status


class InvalidCredentialsError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Invalid email or password.'
    default_code = 'invalid_credentials'


class UserAlreadyExistsError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'A user with this email already exists.'
    default_code = 'user_exists'
```

---

### `admin.py`

**What it does:** Registers the `User` model with Django's admin panel and customizes
how it appears. A basic registration shows the model — a customized registration
shows it like a senior built it.

```python
# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'is_verified', 'is_staff', 'date_joined']
    list_filter = ['is_verified', 'is_staff', 'is_active']
    search_fields = ['email', 'username']
    ordering = ['-date_joined']

    # add our custom fields to the admin form
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile', {'fields': ('phone_number', 'avatar', 'is_verified')}),
    )
```

---

### `tests/`

**What it does:** Unit and integration tests for the accounts app. Split across
files by what they're testing.

`test_models.py` — user creation, password hashing, email uniqueness constraints.
`test_services.py` — register_user, authenticate_user, change_password logic.
`test_views.py` — API endpoints, status codes, token responses, auth protection.

Django's test runner uses a separate test database — it creates it, runs tests,
destroys it. No test data ever touches your real database.

---

## Data Flow for a Register Request

```
POST /auth/register/
        ↓
  accounts/urls.py         (route match)
        ↓
  RegisterView.create()    (parse request, call serializer)
        ↓
  RegisterSerializer       (validate email, password, confirm_password)
        ↓
  services.register_user() (check uniqueness, create user)
        ↓
  User.objects.create()    (ORM — writes to DB)
        ↓
  post_save signal fires   (welcome email side effect)
        ↓
  services.generate_tokens() (JWT access + refresh)
        ↓
  Response(tokens, 201)    (back to client)
```

---

## Dependencies to Install

```bash
uv pip install djangorestframework-simplejwt
```

Add to `INSTALLED_APPS` in `base.py`:
```python
'rest_framework',
'rest_framework_simplejwt',
'rest_framework_simplejwt.token_blacklist',  # for logout (token blacklisting)
```

Add to `base.py` (DRF global config):
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}
```

---

## What You Will NOT Find Here

- Any shortener logic — zero coupling
- Template rendering — this is an API app, responses are JSON only
- Session-based auth — JWT only, stateless
- Hard-coded user data — everything flows through serializers and services
