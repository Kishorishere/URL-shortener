import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.db import models

from shortener.cache import get_cached_url, set_cached_url
from shortener.models import ShortenedURL

logger = logging.getLogger(__name__)


def resolve_short_code(code: str) -> ShortenedURL | None:
    cached = get_cached_url(code)
    if cached is not None:
        return ShortenedURL(**cached)

    try:
        url = ShortenedURL.objects.select_related("domain").get(
            models.Q(short_code=code) | models.Q(custom_slug=code),
            is_active=True,
            deleted_at__isnull=True,
        )
        set_cached_url(code, {
            "id": url.pk,
            "original_url": url.original_url,
            "password": url.password,
            "expires_at": url.expires_at,
            "show_preview": url.show_preview,
            "click_count": url.click_count,
            "utm_source": url.utm_source,
            "utm_medium": url.utm_medium,
            "utm_campaign": url.utm_campaign,
            "utm_term": url.utm_term,
            "utm_content": url.utm_content,
        })
        return url
    except ShortenedURL.DoesNotExist:
        logger.info("Short code not found: %s", code)
        return None


def build_redirect_url(url: ShortenedURL) -> str:
    parsed = urlparse(url.original_url)
    params = parse_qs(parsed.query)

    utm_fields = {
        "utm_source": url.utm_source,
        "utm_medium": url.utm_medium,
        "utm_campaign": url.utm_campaign,
        "utm_term": url.utm_term,
        "utm_content": url.utm_content,
    }
    for key, value in utm_fields.items():
        if value:
            params[key] = [value]

    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))
