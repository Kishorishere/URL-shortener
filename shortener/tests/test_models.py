from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from shortener.models import APIKey, ClickEvent, ShortenedURL

User = get_user_model()


class ShortenedURLModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            username="testuser",
        )
        self.url = ShortenedURL.objects.create(
            user=self.user,
            original_url="https://example.com/very/long/path",
            short_code="abc123",
        )

    def test_active_code_uses_custom_slug(self):
        self.url.custom_slug = "my-slug"
        self.assertEqual(self.url.active_code, "my-slug")

    def test_active_code_falls_back_to_short_code(self):
        self.assertEqual(self.url.active_code, "abc123")

    def test_is_expired_no_expiry(self):
        self.assertFalse(self.url.is_expired)

    def test_is_expired_with_future_expiry(self):
        self.url.expires_at = timezone.now() + timezone.timedelta(days=1)
        self.assertFalse(self.url.is_expired)

    def test_is_expired_with_past_expiry(self):
        self.url.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.assertTrue(self.url.is_expired)

    def test_password_protection(self):
        self.assertFalse(self.url.is_password_protected)
        self.url.set_password("secret")
        self.assertTrue(self.url.is_password_protected)
        self.assertTrue(self.url.check_password("secret"))
        self.assertFalse(self.url.check_password("wrong"))

    def test_soft_delete_and_restore(self):
        self.assertTrue(self.url.is_active)
        self.assertIsNone(self.url.deleted_at)
        self.url.soft_delete()
        self.assertFalse(self.url.is_active)
        self.assertIsNotNone(self.url.deleted_at)
        self.assertTrue(self.url.is_deleted)
        self.url.restore()
        self.assertTrue(self.url.is_active)
        self.assertIsNone(self.url.deleted_at)

    def test_str_representation(self):
        self.assertIn("abc123", str(self.url))


class APIKeyModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="apikey@example.com",
            password="testpass123",
            username="apikeyuser",
        )

    def test_generate_creates_key(self):
        key_obj = APIKey.generate(self.user, "My App")
        self.assertEqual(key_obj.name, "My App")
        self.assertEqual(key_obj.user, self.user)
        self.assertEqual(len(key_obj.key), 43)
        self.assertTrue(key_obj.is_active)
