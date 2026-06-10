from django.core.cache import cache

CACHE_PREFIX = "shortener:"
REDIRECT_TTL = 3600


def get_cached_url(code: str) -> str | None:
    key = f"{CACHE_PREFIX}url:{code}"
    return cache.get(key)


def set_cached_url(code: str, url_data: dict) -> None:
    key = f"{CACHE_PREFIX}url:{code}"
    cache.set(key, url_data, REDIRECT_TTL)


def invalidate_url_cache(code: str) -> None:
    key = f"{CACHE_PREFIX}url:{code}"
    cache.delete(key)
