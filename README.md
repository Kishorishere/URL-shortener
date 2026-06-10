# URL Shortener

A production-grade URL shortening service built with Django. Goes beyond basic redirects — features **OIDC + JWT authentication**, **geo-coded click analytics**, **QR code generation**, **custom slugs**, **password-protected links**, **expiration dates**, **UTM tracking**, **custom domains**, and a full **REST API**. Designed for real-world deployment (Render, Railway, or any VPS).

## Tech Stack

| Layer | Choice |
|-------|--------|
| **Framework** | Django 6.0 + Django REST Framework 3.17 |
| **Auth** | SimpleJWT (access/refresh tokens), cookie-based JWT, Google OIDC, API key auth |
| **Database** | PostgreSQL (production) / SQLite (dev) |
| **QR Codes** | `qrcode` + Pillow — PNG & SVG download |
| **Geo IP** | `geoip2` — country/city resolution per click |
| **User Agent Parsing** | `user-agents` — browser, OS, device type |
| **Async DNS** | `dnspython` — domain verification |
| **Caching** | LocMem (dev) / Redis (production opt-in) |
| **Server** | Gunicorn + Whitenoise (production) |
| **E2E Tests** | Playwright (47 tests covering auth, CRUD, API, redirects) |

## What Makes This Stand Out

- **OIDC + JWT auth** — Google sign-in combined with HttpOnly cookie-based JWT tokens. No localStorage secrets. Refresh token rotation + blacklisting included.
- **Custom slugs** — choose your own URL path (e.g. `/my-slug`) instead of random codes. Auto-slugify from title if omitted.
- **QR codes on every link** — auto-generated, downloadable as PNG and SVG, embedded in the analytics page.
- **Geo-coded analytics** — every click records country, city, device type, browser, OS, and referer. Country and device breakdowns in the dashboard.
- **Password-protected links** — gate content behind a password. Django's `make_password`/`check_password` — no plaintext.
- **Expiration with proper HTTP status** — expired links return **410 Gone** instead of a soft redirect.
- **Preview pages** — optional 5-second interstitial before the redirect.
- **UTM builder** — built-in fields for source, medium, campaign, term, and content. Auto-appended to destination URLs.
- **Custom domains** — bring your own domain, verification flow, domain-level routing.
- **REST API** — full CRUD for links, tags, and domains. Authenticate via cookie or API key. Bulk CSV upload endpoint.
- **Trash & restore** — soft delete with 30-day recovery window. After 30 days, permanent expiry.
- **Bulk CSV upload** — create hundreds of links from a single file. Downloadable results with error reporting.
- **Secure by default** — content-length limits, password hashing, no secret exposure, OWASP-friendly session handling.

## Quick Start

```bash
git clone https://github.com/Kishorishere/URL-shortener.git
cd URL-shortener

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

cp .env.example .env
# Edit .env with your settings (at minimum SECRET_KEY and ALLOWED_HOSTS)

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://localhost:8000` — register an account and start shortening.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | Django secret key (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`) |
| `DEBUG` | No | `True` | Debug mode |
| `ALLOWED_HOSTS` | Yes | — | Comma-separated allowed hosts |
| `DJANGO_SETTINGS_MODULE` | No | `config.settings.development` | Settings profile |
| `DATABASE_URL` | No* | — | PostgreSQL connection string (Render auto-injects) |
| `BASE_URL` | No | `http://localhost:8000` | Short URL base domain (used in dashboard and detail pages) |
| `GOOGLE_CLIENT_ID` | No | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | — | Google OAuth client secret |
| `SMTP_HOST` | No | `smtp.gmail.com` | SMTP server |
| `SMTP_USER` | No | — | SMTP username |
| `SMTP_PASS` | No | — | SMTP password / app password |

*Required in production. Falls back to individual `DB_NAME`, `DB_USER`, etc.

## Deployment (Render)

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → connect your repo
3. `render.yaml` is detected — build and start commands are pre-filled
4. Add a PostgreSQL instance: New → PostgreSQL (free tier)
5. Set env vars in the Render dashboard:
   - `DJANGO_SETTINGS_MODULE` = `config.settings.production`
   - `SECRET_KEY` — generate a secure one
   - `ALLOWED_HOSTS` = `.onrender.com`
   - `BASE_URL`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` = your app URL
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SMTP_*` as needed
6. Deploy

## Tests

```bash
# Unit / integration tests
python manage.py test shortener accounts

# E2E tests (requires Playwright)
cd e2e
npm install
npx playwright test
```
