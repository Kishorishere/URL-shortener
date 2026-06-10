# `shortener` App — Build Summary

## Status: ✅ 61 tests passing, system check clean

---

## File Manifest

```
shortener/
├── __init__.py
├── apps.py                    — AppConfig, imports signals in ready()
├── admin.py                  — ShortenedURLAdmin, ClickEventAdmin, TagAdmin, DomainAdmin, APIKeyAdmin
├── models.py                 — ShortenedURL, ClickEvent, Tag, Domain, APIKey
├── forms.py                  — ShortenedURLForm (with custom slug validation, URL normalization, password hashing)
├── serializers.py            — ShortenedURLSerializer, ShortenedURLCreateSerializer, ClickEventSerializer, APIKeySerializer, DomainSerializer, TagSerializer
├── views.py                  — redirect_view, password_gate_view, dashboard_list/create/edit/detail/delete, bulk, trash, restore, qr_download
├── urls.py                   — Dashboard routes (namespaced `shortener`)
├── api_views.py              — ShortenedURLViewSet, TagViewSet, APIKeyViewSet, DomainViewSet, bulk_create_api
├── api_urls.py               — DRF router + /api/v1/ routes
├── authentication.py         — APIKeyAuthentication (Authorization: Api-Key <key>)
├── middleware.py              — CustomDomainMiddleware (Host header -> Domain lookup)
├── decorators.py             — rate_limit decorator
├── cache.py                  — Cache abstraction (Django cache framework, locmem in dev, swap to Redis)
├── signals.py                — Cache invalidation on URL save/delete, API key logging
├── services/
│   ├── __init__.py
│   ├── shortcode.py          — Random base62 generation + custom slug validation (reserved words list)
│   ├── cleaner.py            — URL normalization (strip tracking params, trailing slash, fragment) + title fetching
│   ├── redirect.py           — resolve_short_code (with cache), build_redirect_url (UTM injection)
│   ├── analytics.py          — log_click (async via threading), get_clicks_over_time, by_country, by_device
│   ├── qr.py                 — QR generation (PNG base64 + SVG bytes)
│   ├── bulk.py               — CSV bulk processing
│   └── domain_verifier.py    — DNS TXT verification (with fallback when dnspython not installed)
├── utils/
│   ├── __init__.py
│   ├── useragent.py          — Parse UA via user_agents library
│   └── geo.py                — IP -> country via GeoIP2 (MaxMind) with ip-api.com fallback
├── management/
│   └── commands/
│       ├── cleanup_expired.py — Deactivates expired URLs
│       └── cleanup_clicks.py  — Deletes old click events (configurable retention)
├── templates/shortener/
│   ├── base.html              — Nav, messages, tailwind
│   ├── list.html              — Paginated link table
│   ├── form.html              — Create/Edit form
│   ├── detail.html            — Stats, QR code, analytics charts
│   ├── bulk.html              — CSV upload
│   ├── trash.html             — Soft-deleted links with restore
│   ├── confirm_delete.html    — Trash confirmation
│   ├── confirm_restore.html   — Restore confirmation
│   ├── password_gate.html     — Password entry
│   ├── preview.html           — Redirect preview page
│   ├── 404.html               — Link not found
│   └── expired.html           — Link expired (410)
├── tests/
│   ├── __init__.py
│   ├── test_models.py         — 9 tests (ShortenedURL + APIKey methods)
│   ├── test_services.py       — 18 tests (code gen, URL cleaning, redirect, analytics)
│   ├── test_redirect.py       — 8 tests (redirect flow, 302, 404, 410, password, preview, cache headers)
│   └── test_analytics.py      — 4 tests (aggregation queries)
└── migrations/
    ├── __init__.py
    └── 0001_initial.py
```

---

## Data Model

| Model | Purpose | Key Fields |
|---|---|---|
| `ShortenedURL` | One row per short link | `short_code`, `custom_slug`, `original_url`, `password` (hashed), `click_count`, `expires_at`, `deleted_at`, UTM fields, `tags` (M2M) |
| `ClickEvent` | One row per click | `url` (FK), `clicked_at`, `ip_address`, `country`, `browser`, `os`, `device_type`, `referer_domain` |
| `Tag` | User-scoped labels | `user` (FK), `name`, `color` |
| `Domain` | Custom branded domains | `domain`, `is_verified`, `verification_token` |
| `APIKey` | Programmatic access | `key` (crypto-random), `name`, `is_active`, `last_used_at` |

### Senior Design Decisions

| Decision | Why |
|---|---|
| **Soft delete** (`deleted_at`) | Users get a 30-day recovery window; accidental deletes aren't permanent |
| **Denormalized `click_count`** | Dashboard loads instantly without counting ClickEvent rows; `F()` expressions keep it atomic |
| **Async click logging** (`threading.Thread`) | Redirect doesn't wait for analytics DB writes — cuts latency |
| **Cache abstraction** | Swap from `LocMemCache` to Redis with one setting change; URL cache invalidated via signals |
| **`F()` for counter updates** | `ShortenedURL.objects.filter(pk=x).update(click_count=F('click_count')+1)` — race-condition-safe |
| **Password hashing** | Uses Django's `make_password`/`check_password`, never plaintext |
| **API keys via `secrets.token_urlsafe`** | Cryptographically random, URL-safe, no padding |
| **Reserved slugs set** | Blocks `/api`, `/admin`, `/auth`, etc. from being used as custom slugs |
| **UTM injection** | Stored on the URL model, injected at redirect time via `build_redirect_url()` |
| **Geo IP with fallback** | GeoIP2 (MaxMind) primary, `ip-api.com` fallback when mmdb file is absent |

---

## API Endpoints

### Public

| Method | Path | Purpose |
|---|---|---|
| GET | `/<code>/` | Redirect (302) to original URL |
| GET | `/password/<code>/` | Password gate form |
| GET/POST | `/password/<code>/` | Submit password, unlock session |

### Dashboard (authenticated, server-rendered)

| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard/` | Paginated link list |
| GET/POST | `/dashboard/create/` | Create short URL |
| GET | `/dashboard/<code>/` | Detail + analytics + QR |
| GET/POST | `/dashboard/<code>/edit/` | Edit |
| POST | `/dashboard/<code>/delete/` | Soft delete |
| POST | `/dashboard/<code>/restore/` | Restore from trash |
| GET/POST | `/dashboard/bulk/` | CSV upload |
| GET | `/dashboard/trash/` | Deleted links |
| GET | `/dashboard/<code>/qr/<format>/` | QR download (png/svg) |

### REST API (authenticated)

| Method | Path | Purpose |
|---|---|---|
| CRUD | `/api/v1/links/` | ShortenedURL CRUD |
| GET | `/api/v1/links/{id}/clicks/` | Click events |
| GET | `/api/v1/links/{id}/qr/` | QR code (format param) |
| POST | `/api/v1/links/{id}/soft_delete/` | Soft delete |
| CRUD | `/api/v1/tags/` | Tags |
| CRUD | `/api/v1/api-keys/` | API keys |
| CRUD | `/api/v1/domains/` | Custom domains |
| POST | `/api/v1/bulk/` | Bulk CSV upload |

### Auth (from `accounts`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register/` | Register + set cookies |
| POST | `/api/auth/login/` | Login + set cookies |
| POST | `/api/auth/logout/` | Clear cookies + blacklist |
| GET | `/api/auth/profile/` | User profile |
| POST | `/api/auth/change-password/` | Change password |
| POST | `/api/auth/token/refresh/` | Refresh tokens |

Authentication order: cookie → bearer → API key (three-tier fallback).

---

## URL Routing Priority

```python
/admin/           # admin
/api/auth/        # accounts
/api/v1/          # shortener API
/dashboard/       # shortener dashboard
/password/<str>/  # password gate
/<str>/           # redirect (catch-all — MUST be last)
```

---

## Management Commands

```bash
python manage.py cleanup_expired     # Deactivate expired URLs
python manage.py cleanup_clicks      # Delete click events older than N days (default: 365)
```

---

## Settings Changes

In `config/settings/base.py`:
- `INSTALLED_APPS` — added `shortener`
- `MIDDLEWARE` — added `shortener.middleware.CustomDomainMiddleware`
- `REST_FRAMEWORK` — added `APIKeyAuthentication`, pagination config
- `CACHES` — `LocMemCache` for dev
- `GEOIP_PATH` — `BASE_DIR / 'geoip'`
- `LOGGING` — stream handler for all modules

---

## Running the App

```powershell
# Set env and run
$env:DJANGO_SETTINGS_MODULE='config.settings.development'
python manage.py migrate
python manage.py runserver

# Test
python manage.py test accounts
python manage.py test shortener.tests.test_models shortener.tests.test_services shortener.tests.test_redirect shortener.tests.test_analytics

# Management
python manage.py cleanup_expired
python manage.py cleanup_clicks --days 180
```
