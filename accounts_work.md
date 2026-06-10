# `accounts` App — Build Summary

## Status: ✅ All 25 tests passing

---

## File Manifest

```
accounts/
├── __init__.py
├── apps.py              — AppConfig, imports signals in ready()
├── admin.py             — Custom UserAdmin with profile fieldsets
├── models.py            — User(AbstractUser), email as USERNAME_FIELD
├── managers.py          — UserManager, create_user / create_superuser
├── serializers.py       — Register, Login, Profile, ChangePassword
├── views.py             — RegisterView, LoginView, LogoutView, ProfileView, ChangePasswordView, TokenRefreshView
├── urls.py              — /register/, /login/, /logout/, /profile/, /change-password/, /token/refresh/
├── services.py          — register_user, authenticate_user, generate_tokens, change_password, post_auth_hook
├── authentication.py    — CookieJWTAuthentication (reads access_token cookie)
├── permissions.py       — IsVerifiedUser
├── exceptions.py        — InvalidCredentialsError (401), UserAlreadyExistsError (409)
├── signals.py           — post_save on User (welcome log)
├── tests/
│   ├── __init__.py
│   ├── test_models.py   — 5 tests
│   ├── test_services.py — 7 tests
│   └── test_views.py    — 13 tests
└── migrations/
    ├── __init__.py
    └── 0001_initial.py
```

---

## Authentication Strategy

**HttpOnly cookies** instead of bearer tokens in response bodies.

| Cookie | Path | Max-Age | httponly | samesite |
|---|---|---|---|---|
| `access_token` | `/` | 15 min | ✅ | Lax |
| `refresh_token` | `/api/auth/token/refresh/` | 7 days | ✅ | Lax |

`secure` is controlled by `settings.SECURE_COOKIE` (False in dev).

### Flow

```
Register/Login → generate JWT pair → set both as HttpOnly cookies → return user profile (no tokens in body)
Every request  → CookieJWTAuthentication reads access_token cookie → validates → attaches request.user
Refresh        → POST /api/auth/token/refresh/ → reads refresh_token cookie → rotates access_token
Logout         → blacklists refresh token → clears both cookies
```

Fallback: `JWTAuthentication` (header-based) is still configured as a secondary auth class for programmatic clients.

---

## API Endpoints

| Method | Path | Auth | Response |
|---|---|---|---|
| POST | `/api/auth/register/` | AllowAny | 201 + user profile + cookies |
| POST | `/api/auth/login/` | AllowAny | 200 + user profile + cookies |
| POST | `/api/auth/logout/` | IsAuthenticated | 200 + clears cookies |
| GET | `/api/auth/profile/` | IsAuthenticated | 200 + user profile |
| POST | `/api/auth/change-password/` | IsAuthenticated | 200 |
| POST | `/api/auth/token/refresh/` | AllowAny | 200 + refreshes cookies |

---

## Design Decisions

1. **Service layer** — All business logic lives in `services.py`. Views only handle HTTP. Logic is testable without DRF.
2. **`post_auth_hook(user)`** — No-op in `services.py`. Ready for your "one step up" (OAuth/OIDC/whatever).
3. **ModelSerializer for Register** — Suppresses DRF's auto unique validators via `extra_kwargs` so the service layer controls uniqueness and returns a proper 409.
4. **No username login** — `USERNAME_FIELD = 'email'`. `username` field still exists (Django requirement for `AbstractUser`) but login is email-only.
5. **Reusable** — Zero dependency on `shortener`. Drop `accounts/` + config entries into any project for instant JWT cookie auth.

---

## Settings Changes

In `config/settings/base.py`:
- `AUTH_USER_MODEL = 'accounts.User'`
- `INSTALLED_APPS` — added `rest_framework`, `rest_framework_simplejwt`, `rest_framework_simplejwt.token_blacklist`, `accounts`
- `REST_FRAMEWORK` — `CookieJWTAuthentication` as primary, `JWTAuthentication` as fallback
- `SIMPLE_JWT` — 15-min access, 7-day refresh, blacklist enabled
- `from datetime import timedelta`

In `config/urls.py`:
- `path('api/auth/', include('accounts.urls', namespace='accounts'))`
