from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from shortener.models import ClickEvent, ShortenedURL
from shortener.services.analytics import (
    get_clicks_by_country,
    get_clicks_by_device,
    get_clicks_over_time,
)

User = get_user_model()


class AnalyticsQueryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="analyticsquery@example.com",
            password="testpass123",
            username="analyticsqueryuser",
        )
        self.url = ShortenedURL.objects.create(
            user=self.user,
            original_url="https://example.com",
            short_code="ana222",
        )
        for i in range(5):
            ClickEvent.objects.create(
                url=self.url,
                country="US",
                device_type="desktop",
                clicked_at=timezone.now() - timezone.timedelta(hours=i),
            )
        for i in range(3):
            ClickEvent.objects.create(
                url=self.url,
                country="IN",
                device_type="mobile",
                clicked_at=timezone.now() - timezone.timedelta(hours=i),
            )

    def test_clicks_over_time_returns_data(self):
        results = list(get_clicks_over_time(self.url))
        self.assertTrue(len(results) > 0)

    def test_clicks_by_country_returns_data(self):
        results = list(get_clicks_by_country(self.url))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["country"], "US")
        self.assertEqual(results[0]["count"], 5)

    def test_clicks_by_device_returns_data(self):
        results = list(get_clicks_by_device(self.url))
        device_counts = {r["device_type"]: r["count"] for r in results}
        self.assertEqual(device_counts["desktop"], 5)
        self.assertEqual(device_counts["mobile"], 3)
