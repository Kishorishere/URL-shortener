import logging
import threading
from urllib.parse import urlparse

from django.db.models import Count
from django.db.models.functions import TruncDay
from django.utils import timezone

logger = logging.getLogger(__name__)


def log_click(url, request) -> None:
    threading.Thread(
        target=_log_click_sync,
        args=(url.pk, request),
        daemon=True,
    ).start()


def _log_click_sync(url_pk, request) -> None:
    from django.db import close_old_connections, connection
    from django.db.models import F

    from shortener.models import ClickEvent, ShortenedURL
    from shortener.utils.geo import ip_to_country
    from shortener.utils.useragent import parse_user_agent

    close_old_connections()
    try:
        url = ShortenedURL.objects.get(pk=url_pk)
    except ShortenedURL.DoesNotExist:
        return

    ip = get_client_ip(request)
    ua_data = parse_user_agent(request.META.get("HTTP_USER_AGENT", ""))
    referer = request.META.get("HTTP_REFERER", "")

    try:
        ClickEvent.objects.create(
            url=url,
            ip_address=ip,
            country=ip_to_country(ip),
            city="",
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            browser=ua_data["browser"],
            os=ua_data["os"],
            device_type=ua_data["device_type"],
            referer=referer[:2048],
            referer_domain=extract_domain(referer),
        )
        ShortenedURL.objects.filter(pk=url_pk).update(
            click_count=F("click_count") + 1
        )
    except Exception as e:
        logger.error("Failed to log click for url %s: %s", url_pk, e)


def get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def extract_domain(referer: str) -> str:
    if not referer:
        return ""
    try:
        return urlparse(referer).hostname or ""
    except Exception:
        return ""


def get_clicks_over_time(url, days=30):
    thirty_days_ago = timezone.now() - timezone.timedelta(days=days)
    return (
        url.click_events.filter(clicked_at__gte=thirty_days_ago)
        .annotate(day=TruncDay("clicked_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )


def get_clicks_by_country(url, limit=10):
    return (
        url.click_events.values("country")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )


def get_clicks_by_device(url):
    return (
        url.click_events.values("device_type")
        .annotate(count=Count("id"))
    )
