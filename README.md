# URL Shortener

A Django-based URL shortening service with user authentication, analytics, password-protected links, expiration dates, QR codes, custom slugs, UTM tracking, and a REST API.

## Features

- **Shorten URLs** — custom slugs or auto-generated short codes
- **Password protection** — gate links behind a password
- **Expiration** — set expiry dates (410 Gone after expiry)
- **Preview page** — optional interstitial before redirecting
- **Click analytics** — country, device, browser, referer, time-series charts
- **QR codes** — auto-generated, downloadable as PNG/SVG
- **Tags** — organize and filter links in the dashboard
- **UTM builder** — append tracking params to destination URLs
- **Bulk upload** — create many links from a CSV file
- **REST API** — full CRUD via DRF, API key auth, cookie auth
- **Google OAuth** — sign in with Google
- **Trash & restore** — soft delete with 30-day recovery window

## Tech Stack

- **Python 3.13** / **Django 6.0** / **DRF 3.17**
- **PostgreSQL** (production) / **SQLite** (development)
- **SimpleJWT** — access + refresh token auth
- **Whitenoise** — static file serving
- **Gunicorn** — production WSGI server
- **Redis** (optional) — caching
- **Playwright** — E2E tests

## Quick Start

```bash
git clone https://github.com/Kishorishere/URL-shortener.git
cd URL-shortener

python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux

cp .env.example .env
# Edit .env with your settings

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Visit `http://localhost:8000` — register an account and start shortening.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | Django secret key |
| `DEBUG` | No | `True` | Debug mode |
| `ALLOWED_HOSTS` | Yes | — | Comma-separated allowed hosts |
| `DATABASE_URL` | No* | — | PostgreSQL connection string (Render auto-injects) |
| `BASE_URL` | No | `http://localhost:8000` | Short URL base domain |
| `GOOGLE_CLIENT_ID` | No | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | — | Google OAuth client secret |
| `SMTP_HOST` | No | `smtp.gmail.com` | SMTP server |
| `SMTP_USER` | No | — | SMTP username |
| `SMTP_PASS` | No | — | SMTP password/app password |

*Required in production. Falls back to individual `DB_NAME`, `DB_USER`, etc.

## Deployment (Render)

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → connect your repo
3. `render.yaml` is detected — build and start commands are pre-filled
4. Add a PostgreSQL instance: New → PostgreSQL (free tier)
5. Set env vars in the Render dashboard:
   - `DJANGO_SETTINGS_MODULE` = `config.settings.production`
   - `SECRET_KEY` — generate one (see below)
   - `ALLOWED_HOSTS` = `.onrender.com`
   - `BASE_URL`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` = your app URL
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SMTP_*` as needed
6. Deploy

```bash
# Generate a secure SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Running Tests

```bash
python manage.py test shortener accounts
```

E2E tests (requires Playwright):

```bash
cd e2e
npm install
npx playwright test
```
