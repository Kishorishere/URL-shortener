from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class RegisterViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:register")

    def test_register_success(self):
        data = {
            "email": "register@example.com",
            "username": "registeruser",
            "password": "Test@1234",
            "confirm_password": "Test@1234",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertEqual(response.data["email"], "register@example.com")

    def test_register_password_mismatch(self):
        data = {
            "email": "mismatch@example.com",
            "username": "mismatchuser",
            "password": "Test@1234",
            "confirm_password": "Diff@1234",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        User.objects.create_user(
            email="dupreg@example.com",
            password="testpass123",
            username="dupreg",
        )
        data = {
            "email": "dupreg@example.com",
            "username": "dupreg2",
            "password": "Test@1234",
            "confirm_password": "Test@1234",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:login")
        self.user = User.objects.create_user(
            email="login@example.com",
            password="testpass123",
            username="loginuser",
        )
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])

    def test_login_success(self):
        data = {"email": "login@example.com", "password": "testpass123"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

    def test_login_wrong_password(self):
        data = {"email": "login@example.com", "password": "wrongpass"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_email(self):
        data = {"email": "nobody@example.com", "password": "testpass123"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:profile")
        self.user = User.objects.create_user(
            email="profile@example.com",
            password="testpass123",
            username="profileuser",
        )

    def test_profile_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "profile@example.com")

    def test_profile_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ChangePasswordViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:change-password")
        self.user = User.objects.create_user(
            email="changepw@example.com",
            password="oldpass123",
            username="changepwuser",
        )
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        data = {"old_password": "oldpass123", "new_password": "New@456!"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old(self):
        data = {"old_password": "wrongold", "new_password": "New@456!"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:logout")
        self.user = User.objects.create_user(
            email="logout@example.com",
            password="testpass123",
            username="logoutuser",
        )

    def test_logout_authenticated(self):
        self.client.force_authenticate(user=self.user)
        self.client.cookies["refresh_token"] = "dummy"
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)


class TokenRefreshViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:token-refresh")

    def test_refresh_without_cookie_returns_401(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
