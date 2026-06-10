from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shortener.models import ShortenedURL

User = get_user_model()


class RedirectViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="redirectview@example.com",
            password="testpass123",
            username="redirectviewuser",
        )
        self.url = ShortenedURL.objects.create(
            user=self.user,
            original_url="https://example.com",
            short_code="red123",
        )

    def test_redirect_302(self):
        response = self.client.get(f"/red123/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com")

    def test_redirect_has_no_cache_headers(self):
        response = self.client.get(f"/red123/")
        self.assertIn("Cache-Control", response)
        self.assertIn("no-cache", response["Cache-Control"])

    def test_redirect_404(self):
        response = self.client.get("/nonexist/")
        self.assertEqual(response.status_code, 404)

    def test_redirect_preview(self):
        self.url.show_preview = True
        self.url.save()
        response = self.client.get(f"/red123/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You are being redirected")

    def test_redirect_expired(self):
        from django.utils import timezone
        self.url.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.url.save()
        response = self.client.get(f"/red123/")
        self.assertEqual(response.status_code, 410)

    def test_redirect_password_protected(self):
        self.url.set_password("secret")
        self.url.save()
        response = self.client.get(f"/red123/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("password", response["Location"])

    def test_redirect_with_valid_password_session(self):
        self.url.set_password("secret")
        self.url.save()
        session = self.client.session
        session[f"unlocked_{self.url.id}"] = True
        session.save()
        response = self.client.get(f"/red123/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com")
