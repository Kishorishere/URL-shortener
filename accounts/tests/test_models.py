from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_with_email(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_verified)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_verified)

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="testpass123")

    def test_email_uniqueness(self):
        User.objects.create_user(email="same@example.com", password="testpass123")
        with self.assertRaises(Exception):
            User.objects.create_user(email="same@example.com", password="testpass456")

    def test_user_str_is_email(self):
        user = User.objects.create_user(email="str@example.com", password="testpass123")
        self.assertEqual(str(user), "str@example.com")
