import functools
import time

from django.core.cache import cache
from django.http import HttpResponseTooManyRequests


def rate_limit(key_prefix: str, limit: int = 60, window: int = 60):
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            identifier = getattr(request.user, "pk", None) or get_client_ip(request)
            cache_key = f"ratelimit:{key_prefix}:{identifier}"
            hits = cache.get(cache_key, 0)
            if hits >= limit:
                return HttpResponseTooManyRequests("Rate limit exceeded.")
            cache.set(cache_key, hits + 1, window)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
