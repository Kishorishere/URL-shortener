import random
import re
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


def slugify_title(title: str, exclude_id: int | None = None) -> str:
    slug = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-"))
    slug = re.sub(r"-+", "-", slug).strip("-")
    if len(slug) < 3:
        slug = (slug or "link") + "-" + generate_short_code(4)
    qs = ShortenedURL.objects.filter(custom_slug=slug, is_active=True)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        slug = slug + "-" + generate_short_code(4)
    return slug
