import logging
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign",
    "utm_term", "utm_content", "fbclid", "gclid",
    "ref", "source", "si", "mc_cid", "mc_eid",
}


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise ValueError("URL must not be empty.")
    if " " in url:
        raise ValueError("URL must not contain spaces.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    query_pairs = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                if k.lower() not in TRACKING_PARAMS:
                    query_pairs.append((k, v))
            elif pair:
                query_pairs.append((pair, ""))
    clean_parsed = parsed._replace(
        path=parsed.path.rstrip("/") or "/",
        query=urlencode(query_pairs) if query_pairs else "",
        fragment="",
    )
    return urlunparse(clean_parsed)


def fetch_page_title(url: str, timeout: int = 5) -> str:
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "URLShortener/1.0"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        content = resp.text
        start = content.lower().find("<title>")
        if start == -1:
            return ""
        end = content.lower().find("</title>", start)
        if end == -1:
            return ""
        return content[start + 7 : end].strip()[:255]
    except Exception as e:
        logger.warning("Failed to fetch title for %s: %s", url, e)
        return ""
