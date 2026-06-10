import random
import string

from shortener.models import ShortenedURL

ALPHABET = string.ascii_letters + string.digits
DEFAULT_LENGTH = 6

RESERVED_SLUGS = {
    "api", "admin", "auth", "static", "media", "dashboard",
    "login", "register", "logout", "profile", "account",
    "health", "status", "docs", "help", "support",
    "favicon.ico", "robots.txt", "sitemap.xml",
}


def generate_short_code(length=DEFAULT_LENGTH) -> str:
    for _ in range(10):
        code = "".join(random.choices(ALPHABET, k=length))
        if not ShortenedURL.objects.filter(short_code=code).exists():
            return code
    return generate_short_code(length + 1)


def validate_custom_slug(slug: str) -> str | None:
    slug = slug.strip().lower()
    if len(slug) < 3 or len(slug) > 50:
        return "Slug must be between 3 and 50 characters."
    if not slug.replace("-", "").isalnum():
        return "Slug can only contain letters, numbers, and hyphens."
    if slug in RESERVED_SLUGS:
        return "This slug is reserved and cannot be used."
    if ShortenedURL.objects.filter(
        custom_slug=slug, is_active=True
    ).exists():
        return "This slug is already taken."
    return None
