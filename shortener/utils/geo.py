import logging
from pathlib import Path

from django.conf import settings

import requests

logger = logging.getLogger(__name__)

GEOIP_DB_PATH = getattr(settings, "GEOIP_PATH", Path("geoip"))


def ip_to_country(ip: str) -> str:
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return ""
    result = _geoip2_lookup(ip)
    if result:
        return result
    return _ipapi_fallback(ip)


def _geoip2_lookup(ip: str) -> str | None:
    try:
        mmdb = GEOIP_DB_PATH / "GeoLite2-Country.mmdb"
        if not mmdb.exists():
            return None
        import geoip2.database
        with geoip2.database.Reader(str(mmdb)) as reader:
            response = reader.country(ip)
            return response.country.iso_code or ""
    except Exception as e:
        logger.debug("GeoIP2 lookup failed for %s: %s", ip, e)
        return None


def _ipapi_fallback(ip: str) -> str:
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            timeout=3,
            params={"fields": "countryCode"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("countryCode", "")
    except Exception as e:
        logger.debug("ip-api.com fallback failed for %s: %s", ip, e)
        return ""
