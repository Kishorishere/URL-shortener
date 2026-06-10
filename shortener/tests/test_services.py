from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory

from shortener.models import ClickEvent, ShortenedURL
from shortener.services.analytics import (
    _log_click_sync,
    get_client_ip,
    get_clicks_by_country,
    get_clicks_by_device,
    get_clicks_over_time,
)
from shortener.services.cleaner import fetch_page_title, normalize_url
from shortener.services.redirect import build_redirect_url, resolve_short_code
from shortener.services.shortcode import generate_short_code, validate_custom_slug

User = get_user_model()


class ShortCodeTests(TestCase):
    def test_generates_unique_code(self):
        code = generate_short_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isalnum())

    def test_validate_custom_slug_valid(self):
        self.assertIsNone(validate_custom_slug("my-slug"))

    def test_validate_custom_slug_too_short(self):
        self.assertIsNotNone(validate_custom_slug("ab"))

    def test_validate_custom_slug_reserved(self):
        self.assertIsNotNone(validate_custom_slug("api"))
        self.assertIsNotNone(validate_custom_slug("admin"))


class NormalizeURLTests(TestCase):
    def test_adds_https(self):
        self.assertEqual(
            normalize_url("example.com"),
            "https://example.com/",
        )

    def test_removes_utm_params(self):
        result = normalize_url(
            "https://example.com/page?utm_source=twitter&foo=bar"
        )
        self.assertIn("foo=bar", result)
        self.assertNotIn("utm_source", result)

    def test_strips_fragment(self):
        result = normalize_url("https://example.com/page#section")
        self.assertNotIn("#section", result)


class RedirectServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="redirect@example.com",
            password="testpass123",
            username="redirectuser",
        )
        self.url = ShortenedURL.objects.create(
            user=self.user,
            original_url="https://example.com",
            short_code="xyz789",
        )

    def test_resolve_by_short_code(self):
        result = resolve_short_code("xyz789")
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.url.pk)

    def test_resolve_nonexistent_code(self):
        self.assertIsNone(resolve_short_code("nonexist"))

    def test_build_redirect_url_without_utm(self):
        result = build_redirect_url(self.url)
        self.assertEqual(result, "https://example.com")

    def test_build_redirect_url_with_utm(self):
        self.url.utm_source = "twitter"
        self.url.utm_medium = "social"
        result = build_redirect_url(self.url)
        self.assertIn("utm_source=twitter", result)
        self.assertIn("utm_medium=social", result)


class AnalyticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="analytics@example.com",
            password="testpass123",
            username="analyticsuser",
        )
        self.url = ShortenedURL.objects.create(
            user=self.user,
            original_url="https://example.com",
            short_code="ana111",
        )
        self.factory = RequestFactory()

    def test_log_click_creates_event(self):
        request = self.factory.get("/")
        _log_click_sync(self.url.pk, request)
        self.url.refresh_from_db()
        self.assertEqual(self.url.click_count, 1)

    def test_get_client_ip_from_remote_addr(self):
        request = self.factory.get("/", REMOTE_ADDR="192.168.1.1")
        self.assertEqual(get_client_ip(request), "192.168.1.1")

    def test_get_client_ip_from_forwarded(self):
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="10.0.0.1, 10.0.0.2")
        self.assertEqual(get_client_ip(request), "10.0.0.1")

    def test_clicks_over_time_returns_query(self):
        results = get_clicks_over_time(self.url)
        self.assertEqual(len(list(results)), 0)

    def test_clicks_by_country_returns_query(self):
        results = get_clicks_by_country(self.url)
        self.assertEqual(len(list(results)), 0)

    def test_clicks_by_device_returns_query(self):
        results = get_clicks_by_device(self.url)
        self.assertEqual(len(list(results)), 0)
