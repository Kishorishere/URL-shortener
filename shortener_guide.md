# `shortener` App — Senior Implementation Guide

## How Industry URL Shorteners Actually Work

Before writing a line of code, understand the core contract:

```
User hits short URL
      ↓
Your server receives the request
      ↓
Look up the short code in DB (or cache — Redis first, DB fallback)
      ↓
Run checks (expired? password protected? active?)
      ↓
Log the click asynchronously (don't make the user wait for analytics)
      ↓
Return HTTP 302 → original URL
      ↓
User's browser follows redirect
      ↓
User never sees your server again
```

The entire redirect path must be as fast as possible. Every millisecond you add
is a millisecond of latency the user feels. This is why production shorteners
(Bitly, TinyURL) use Redis caching — DB lookup on every redirect doesn't scale.

---

## App Structure

```
shortener/
├── __init__.py
├── apps.py
├── admin.py
├── models.py            — ShortenedURL, ClickEvent, Tag, APIKey, Domain
├── serializers.py       — for DRF API endpoints
├── views.py             — redirect view, dashboard views, API views
├── urls.py
├── services/
│   ├── __init__.py
│   ├── shortcode.py     — code generation logic
│   ├── redirect.py      — redirect logic, click logging
│   ├── analytics.py     — analytics aggregation
│   ├── qr.py            — QR code generation
│   └── bulk.py          — CSV bulk shortening
├── middleware.py        — custom domain resolution
├── tasks.py             — async tasks (Celery) or sync fallback
├── utils/
│   ├── __init__.py
│   ├── useragent.py     — parse device/browser from user agent
│   └── geo.py           — IP to country lookup
├── management/
│   └── commands/
│       └── cleanup_expired.py
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   ├── test_redirect.py
│   └── test_analytics.py
└── migrations/
```

---

## The Data Model — Think Before You Code

This is the most important section. Get the models wrong and everything downstream
is painful. Get them right and features build naturally on top.

### `ShortenedURL`

The core table. One row per short link.

```python
class ShortenedURL(models.Model):
    # ownership
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shortened_urls'
    )

    # the link itself
    original_url = models.URLField(max_length=2048)
    short_code = models.CharField(max_length=20, unique=True, db_index=True)
    # db_index=True is critical — every redirect does a lookup on this field

    # custom slug (bonus feature)
    custom_slug = models.CharField(max_length=50, unique=True, null=True, blank=True)

    # domain (for custom branded domains)
    domain = models.ForeignKey(
        'Domain',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='urls'
    )

    # tags / groups
    tags = models.ManyToManyField('Tag', blank=True, related_name='urls')

    # metadata
    title = models.CharField(max_length=255, blank=True)  # auto-fetched from og:title
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # state
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # None = never expires

    # password protection
    password = models.CharField(max_length=255, blank=True)
    # store hashed, not plaintext — use Django's make_password / check_password

    # link preview toggle
    show_preview = models.BooleanField(default=False)

    # UTM parameters — stored as JSON, injected at redirect time
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    utm_term = models.CharField(max_length=100, blank=True)
    utm_content = models.CharField(max_length=100, blank=True)

    # denormalized click count — updated on every click for fast dashboard queries
    # the real source of truth is ClickEvent, but querying COUNT(*) on every
    # dashboard load is expensive at scale. Keep this in sync via signals.
    click_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'shortener_url'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['short_code']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['expires_at']),
        ]

    @property
    def active_code(self):
        # custom slug takes priority over auto-generated code
        return self.custom_slug or self.short_code

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_password_protected(self):
        return bool(self.password)

    def __str__(self):
        return f'{self.active_code} → {self.original_url[:50]}'
```

### `ClickEvent`

One row per click. This is your raw analytics data. Never aggregate here —
store everything, aggregate at query time or via periodic tasks.

```python
class ClickEvent(models.Model):
    url = models.ForeignKey(
        ShortenedURL,
        on_delete=models.CASCADE,
        related_name='click_events'
    )

    # when
    clicked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # where from
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)   # ISO 3166-1 alpha-2
    city = models.CharField(max_length=100, blank=True)

    # what device
    user_agent = models.TextField(blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    device_type = models.CharField(
        max_length=10,
        choices=[('desktop', 'Desktop'), ('mobile', 'Mobile'), ('tablet', 'Tablet')],
        blank=True
    )

    # referrer
    referer = models.URLField(max_length=2048, blank=True)
    referer_domain = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'shortener_click'
        indexes = [
            models.Index(fields=['url', 'clicked_at']),
            models.Index(fields=['url', 'country']),
            models.Index(fields=['url', 'device_type']),
        ]
```

### `Tag`

Simple. Belongs to a user so tags are private per account.

```python
class Tag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#6366f1')  # hex color for UI

    class Meta:
        db_table = 'shortener_tag'
        unique_together = ['user', 'name']
```

### `Domain`

For custom branded domains. A user registers their domain here.
The actual domain resolution happens in middleware.

```python
class Domain(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    domain = models.CharField(max_length=253, unique=True)
    is_verified = models.BooleanField(default=False)
    # verification: user adds a TXT record to their DNS
    # you generate a token, they add it, you verify via DNS lookup
    verification_token = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shortener_domain'
```

### `APIKey`

For programmatic access. Each user can generate API keys.

```python
import secrets

class APIKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # "My app", "CLI tool" etc.
    key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'shortener_apikey'

    @classmethod
    def generate(cls, user, name):
        key = secrets.token_urlsafe(32)  # cryptographically random
        return cls.objects.create(user=user, name=name, key=key)
```

---

## Feature 1 — Short Code Generation

**How it works in production systems:**

Option A — Auto-increment ID + base62 encode
Take the database row's auto-increment ID. Encode it in base62.
ID 1 → "1", ID 100 → "1C", ID 1000000 → "4c92".
Predictable, sequential, no collision possible. Downside: exposes volume
(someone can guess `id=1` exists and enumerate your links).

Option B — Random base62
Generate a random 6-8 character base62 string. Check DB for collision.
Retry if collision. Collision probability at 6 chars with 56B combinations
is negligible until you have millions of links.

Option C — Hash-based
Hash the long URL (MD5/SHA256), take the first N characters of the base62
representation. Same URL always produces the same code — easy deduplication.
Downside: two different users shortening the same URL get the same code,
which breaks per-user ownership.

**For this project, use Option B.** It's the industry standard for user-owned links.

```python
# services/shortcode.py
import random
import string
from shortener.models import ShortenedURL

ALPHABET = string.ascii_letters + string.digits  # a-z A-Z 0-9 = 62 chars
DEFAULT_LENGTH = 6


def generate_short_code(length=DEFAULT_LENGTH) -> str:
    """
    Generate a unique random base62 short code.
    Retries automatically on collision (astronomically rare at 6 chars).
    """
    for _ in range(10):  # max 10 attempts
        code = ''.join(random.choices(ALPHABET, k=length))
        if not ShortenedURL.objects.filter(short_code=code).exists():
            return code
    # if 10 attempts all collide (statistically impossible at normal scale),
    # try a longer code
    return generate_short_code(length + 1)
```

**Custom slugs:** User provides their own string. You validate:
- Length 3-50 characters
- Only alphanumeric + hyphens
- Not in a reserved words list (`api`, `admin`, `auth`, `static`, `media`)
- Not already taken

---

## Feature 2 — The Redirect View

This is the hottest code path in the entire app. Every single click goes through here.
Keep it lean. Cache aggressively.

```python
# services/redirect.py

def resolve_short_code(code: str) -> ShortenedURL | None:
    """
    Look up a ShortenedURL by code or custom slug.
    In production: check Redis cache first, fall back to DB, write to cache.
    For this project: DB only is fine, cache is a bonus.
    """
    try:
        return ShortenedURL.objects.select_related('domain').get(
            models.Q(short_code=code) | models.Q(custom_slug=code),
            is_active=True
        )
    except ShortenedURL.DoesNotExist:
        return None


def build_redirect_url(url: ShortenedURL) -> str:
    """
    Inject UTM parameters into the original URL if configured.
    """
    from urllib.parse import urlparse, urlencode, urlunparse, parse_qs

    parsed = urlparse(url.original_url)
    params = parse_qs(parsed.query)

    if url.utm_source:
        params['utm_source'] = [url.utm_source]
    if url.utm_medium:
        params['utm_medium'] = [url.utm_medium]
    if url.utm_campaign:
        params['utm_campaign'] = [url.utm_campaign]
    if url.utm_term:
        params['utm_term'] = [url.utm_term]
    if url.utm_content:
        params['utm_content'] = [url.utm_content]

    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))
```

```python
# views.py — the redirect view

from django.shortcuts import redirect, render
from django.contrib.auth.hashers import check_password
from .services.redirect import resolve_short_code, build_redirect_url
from .services.analytics import log_click  # async or sync


def redirect_view(request, code):
    url = resolve_short_code(code)

    if not url:
        return render(request, '404.html', status=404)

    if url.is_expired:
        return render(request, 'shortener/expired.html', status=410)

    if url.is_password_protected:
        if not request.session.get(f'unlocked_{url.id}'):
            return redirect('shortener:password_gate', code=code)

    # log the click — ideally async, sync is fine for this project
    log_click(url, request)

    if url.show_preview:
        return render(request, 'shortener/preview.html', {'url': url})

    destination = build_redirect_url(url)
    return redirect(destination, permanent=False)  # 302, not 301
```

---

## Feature 3 — Click Logging & Analytics

**The logging function:**

```python
# services/analytics.py
from django.utils import timezone
from shortener.models import ClickEvent, ShortenedURL
from shortener.utils.useragent import parse_user_agent
from shortener.utils.geo import ip_to_country


def log_click(url: ShortenedURL, request) -> None:
    ip = get_client_ip(request)
    ua_data = parse_user_agent(request.META.get('HTTP_USER_AGENT', ''))
    referer = request.META.get('HTTP_REFERER', '')

    ClickEvent.objects.create(
        url=url,
        ip_address=ip,
        country=ip_to_country(ip),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        browser=ua_data['browser'],
        os=ua_data['os'],
        device_type=ua_data['device_type'],
        referer=referer[:2048],
        referer_domain=extract_domain(referer),
    )

    # update denormalized count atomically — F() avoids race conditions
    from django.db.models import F
    ShortenedURL.objects.filter(pk=url.pk).update(click_count=F('click_count') + 1)


def get_client_ip(request) -> str:
    # X-Forwarded-For is set by proxies/load balancers
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
```

**Why `F('click_count') + 1` instead of `url.click_count += 1`?**
If two requests hit simultaneously, both read `click_count = 5`, both write `6`.
You lose a click. `F()` tells Django to do `UPDATE ... SET click_count = click_count + 1`
in the database — atomic, race-condition-safe.

**Analytics aggregation queries:**

```python
# clicks over time (last 30 days, grouped by day)
from django.db.models import Count
from django.db.models.functions import TruncDay

clicks_over_time = (
    ClickEvent.objects
    .filter(url=url, clicked_at__gte=thirty_days_ago)
    .annotate(day=TruncDay('clicked_at'))
    .values('day')
    .annotate(count=Count('id'))
    .order_by('day')
)

# clicks by country
by_country = (
    ClickEvent.objects
    .filter(url=url)
    .values('country')
    .annotate(count=Count('id'))
    .order_by('-count')[:10]
)

# clicks by device
by_device = (
    ClickEvent.objects
    .filter(url=url)
    .values('device_type')
    .annotate(count=Count('id'))
)
```

These are Django ORM aggregations — no raw SQL needed.

---

## Feature 4 — User Agent Parsing

Parse device type, browser, OS from the `User-Agent` header.

Install: `uv pip install user-agents`

```python
# utils/useragent.py
import user_agents


def parse_user_agent(ua_string: str) -> dict:
    if not ua_string:
        return {'browser': '', 'os': '', 'device_type': 'desktop'}

    ua = user_agents.parse(ua_string)

    if ua.is_mobile:
        device_type = 'mobile'
    elif ua.is_tablet:
        device_type = 'tablet'
    else:
        device_type = 'desktop'

    return {
        'browser': ua.browser.family,
        'os': ua.os.family,
        'device_type': device_type,
    }
```

---

## Feature 5 — IP to Country (Geo Lookup)

Two approaches:

**Option A — `geoip2` + MaxMind GeoLite2 database (free, offline)**
Download the GeoLite2-City.mmdb database file from MaxMind.
Install: `uv pip install geoip2`
Django has built-in GeoIP2 support via `django.contrib.gis.geoip2`.
Point `GEOIP_PATH` in settings to the mmdb file directory.

```python
# utils/geo.py
from django.contrib.gis.geoip2 import GeoIP2


def ip_to_country(ip: str) -> str:
    if not ip or ip == '127.0.0.1':
        return ''
    try:
        g = GeoIP2()
        return g.country_code(ip)  # 'US', 'NP', 'IN' etc.
    except Exception:
        return ''
```

**Option B — `ip-api.com` free API (HTTP call, no setup)**
Simpler to start. Slower (network call per click). Fine for low traffic.
In production you'd switch to Option A.

Use Option A for the submission — it's the production approach.

---

## Feature 6 — QR Code Generation

Install: `uv pip install qrcode[pil]`

```python
# services/qr.py
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64


def generate_qr_base64(url: str) -> str:
    """Returns a base64-encoded PNG — embed directly in HTML as <img src='data:...'/>"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()


def generate_qr_svg(url: str) -> bytes:
    """Returns raw SVG bytes — serve as a file download"""
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(url, image_factory=factory)
    buffer = BytesIO()
    img.save(buffer)
    return buffer.getvalue()
```

Expose as an API endpoint:
`GET /api/links/{code}/qr/?format=png` → download PNG
`GET /api/links/{code}/qr/?format=svg` → download SVG

---

## Feature 7 — Bulk Shortening (CSV)

```python
# services/bulk.py
import csv
import io
from .shortcode import generate_short_code
from shortener.models import ShortenedURL


def process_bulk_csv(user, file_obj) -> tuple[list, list]:
    """
    Reads a CSV with a 'url' column.
    Returns (successes, errors).
    Each success: {'original': '...', 'short_code': '...', 'short_url': '...'}
    Each error: {'original': '...', 'error': '...'}
    """
    successes = []
    errors = []

    decoded = file_obj.read().decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))

    if 'url' not in (reader.fieldnames or []):
        raise ValueError("CSV must have a 'url' column header")

    for row in reader:
        original = row.get('url', '').strip()
        if not original:
            continue
        try:
            # basic URL validation
            from django.core.validators import URLValidator
            URLValidator()(original)

            code = generate_short_code()
            ShortenedURL.objects.create(
                user=user,
                original_url=original,
                short_code=code,
            )
            successes.append({'original': original, 'short_code': code})
        except Exception as e:
            errors.append({'original': original, 'error': str(e)})

    return successes, errors
```

The view accepts a file upload, calls `process_bulk_csv`, returns a downloadable
CSV with the results.

---

## Feature 8 — API Key Authentication

Users generate API keys from their dashboard. External clients pass the key
as a header: `Authorization: Api-Key <key>`

Write a custom DRF authentication class:

```python
# authentication.py (add to shortener or accounts)
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from shortener.models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Api-Key '):
            return None  # not our auth scheme, let next authenticator try

        key = auth_header.split(' ', 1)[1].strip()

        try:
            api_key = APIKey.objects.select_related('user').get(
                key=key,
                is_active=True
            )
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API key.')

        # update last used timestamp
        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        return (api_key.user, api_key)  # (user, auth object)
```

Add to `REST_FRAMEWORK` in settings:

```python
'DEFAULT_AUTHENTICATION_CLASSES': [
    'accounts.authentication.CookieJWTAuthentication',
    'rest_framework_simplejwt.authentication.JWTAuthentication',
    'shortener.authentication.APIKeyAuthentication',  # add this
],
```

---

## Feature 9 — Custom Branded Domains

This is the most complex feature. Here's how it works conceptually:

**The problem:** `yourdomain.com/abc123` needs to work even when the request
comes in for `theirbrand.com/abc123`.

**The solution — middleware:**

```python
# middleware.py
from shortener.models import Domain


class CustomDomainMiddleware:
    """
    Intercepts requests for custom domains.
    If the Host header matches a verified custom domain,
    routes the request to the redirect view directly.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]  # strip port

        try:
            domain = Domain.objects.get(domain=host, is_verified=True)
            # inject domain context so the redirect view knows
            request.custom_domain = domain
        except Domain.DoesNotExist:
            request.custom_domain = None

        return self.get_response(request)
```

**DNS setup on the user's side:**
The user adds a CNAME record pointing `theirbrand.com` → `yourdomain.com`.
Your server receives the request with `Host: theirbrand.com`.
Your middleware catches it, looks up the domain, routes appropriately.

**In practice for this submission:**
Implement the model, the middleware, the verification token system.
You won't actually have real custom domains pointing at you (no live server yet),
but the implementation should be complete and correct. Document it in the README.

---

## Feature 10 — Password Protected Links

```python
# views.py
from django.contrib.auth.hashers import make_password, check_password


def password_gate_view(request, code):
    url = resolve_short_code(code)

    if request.method == 'POST':
        entered = request.POST.get('password', '')
        if check_password(entered, url.password):
            request.session[f'unlocked_{url.id}'] = True
            return redirect('shortener:redirect', code=code)
        else:
            return render(request, 'shortener/password_gate.html', {
                'error': 'Incorrect password.',
                'code': code,
            })

    return render(request, 'shortener/password_gate.html', {'code': code})
```

When creating a link with a password, hash it before saving:
```python
url.password = make_password(raw_password)
url.save()
```

---

## Feature 11 — Link Expiration + Cleanup Command

The `is_expired` property handles redirect-time checking.

The management command handles cleaning up the database periodically:

```python
# management/commands/cleanup_expired.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from shortener.models import ShortenedURL


class Command(BaseCommand):
    help = 'Deactivates expired short URLs'

    def handle(self, *args, **options):
        expired = ShortenedURL.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )
        count = expired.update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(f'Deactivated {count} expired URLs')
        )
```

Run it: `python manage.py cleanup_expired`
In production: schedule it with cron or Celery Beat.

---

## The Redirect URL Design

This is a routing decision that matters.

**Option A:** Short URLs live at the root domain
`yourdomain.com/abc123` → redirect

**Option B:** Short URLs live under a prefix
`yourdomain.com/s/abc123` → redirect
API at `yourdomain.com/api/...`
Dashboard at `yourdomain.com/dashboard/...`

**Use Option A.** It's shorter. The whole point is a short URL.

**The catch:** Your root `urls.py` needs to handle the short code pattern
AFTER all other URL prefixes, so it doesn't swallow `/admin/`, `/api/`, `/auth/`.

```python
# config/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls', namespace='accounts')),
    path('api/', include('shortener.api_urls')),     # API endpoints
    path('dashboard/', include('shortener.urls')),   # Dashboard views

    # This MUST be last — catches everything else as a short code
    path('<str:code>/', views.redirect_view, name='redirect'),
]
```

---

## Admin Customization

```python
# admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import ShortenedURL, ClickEvent, Tag, APIKey, Domain


@admin.register(ShortenedURL)
class ShortenedURLAdmin(admin.ModelAdmin):
    list_display = [
        'short_code', 'truncated_original', 'user',
        'click_count', 'is_active', 'expires_at', 'created_at'
    ]
    list_filter = ['is_active', 'show_preview', 'created_at']
    search_fields = ['short_code', 'custom_slug', 'original_url', 'user__email']
    readonly_fields = ['click_count', 'created_at', 'updated_at']
    raw_id_fields = ['user']  # avoids loading all users in a dropdown

    def truncated_original(self, obj):
        return obj.original_url[:60] + '...' if len(obj.original_url) > 60 else obj.original_url
    truncated_original.short_description = 'Original URL'


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ['url', 'clicked_at', 'country', 'device_type', 'browser']
    list_filter = ['device_type', 'country', 'clicked_at']
    readonly_fields = [f.name for f in ClickEvent._meta.fields]  # all read-only
    # click events are immutable — nobody should edit them
```

---

## Signals

```python
# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ShortenedURL


@receiver(post_save, sender=ShortenedURL)
def on_url_created(sender, instance, created, **kwargs):
    if created:
        # could: send notification, trigger cache warm-up, log to audit trail
        pass


@receiver(post_delete, sender=ShortenedURL)
def on_url_deleted(sender, instance, **kwargs):
    # could: invalidate cache entry for this short code
    pass
```

---

## Dependencies Summary

```bash
uv pip install \
  user-agents \        # UA parsing
  qrcode[pil] \        # QR code generation
  Pillow \             # required by qrcode for PNG output
  geoip2               # IP geolocation
```

Download MaxMind GeoLite2-City database (free, requires account at maxmind.com).
Set in settings: `GEOIP_PATH = BASE_DIR / 'geoip'`

---

## Build Order

Do this in order. Each step builds on the previous.

1. Models + migrations (all models at once — avoids migration conflicts)
2. Admin registration (lets you inspect data as you build)
3. Short code generation service
4. Basic create + redirect flow (the core loop working end to end)
5. Click logging
6. User agent parsing + geo lookup
7. Analytics aggregation queries
8. Dashboard views (list, detail, edit, delete)
9. QR code endpoint
10. Password protection
11. Link expiration + cleanup command
12. UTM injection
13. Bulk CSV upload
14. API key model + authentication class
15. DRF API endpoints
16. Custom domain model + middleware
17. Tags

This order matters. Don't build analytics before you have clicks.
Don't build the API before you have working service layer functions to call.

---

## What Makes This Senior-Level

A junior builds the features. A senior builds them correctly.

- `F()` expressions for atomic counter updates, not `+=`
- `db_index=True` on every field that's used in a WHERE clause
- `select_related` on ForeignKey lookups to avoid N+1 queries
- Denormalized `click_count` for fast dashboard, `ClickEvent` as source of truth
- Service layer — redirect view calls services, not raw ORM
- Custom exception classes, not `raise Exception('error')`
- Reserved words list for custom slugs
- `permanent=False` on redirects (302 not 301) for analytics accuracy
- `make_password` / `check_password` for link passwords, never plaintext
- `secrets.token_urlsafe` for API keys, not `uuid4` (url-safe, no padding)
- Management command for cleanup — not a view, not a signal
- All indexes declared explicitly in `Meta.indexes`
