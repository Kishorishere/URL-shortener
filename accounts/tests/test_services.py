from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from accounts.services import (
    authenticate_user,
    change_password,
    generate_tokens,
    register_user,
)

User = get_user_model()


class RegisterUserTests(TestCase):
    def test_register_creates_user(self):
        data = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "testpass123",
            "confirm_password": "testpass123",
        }
        user = register_user(data)
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.check_password("testpass123"))

    def test_register_duplicate_email_raises(self):
        User.objects.create_user(email="dup@example.com", password="testpass123")
        with self.assertRaises(UserAlreadyExistsError):
            register_user({
                "email": "dup@example.com",
                "username": "dupuser",
                "password": "testpass123",
                "confirm_password": "testpass123",
            })


class AuthenticateUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="auth@example.com",
            password="correctpass",
            username="authuser",
        )
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])

    def test_valid_credentials_returns_user(self):
        user = authenticate_user("auth@example.com", "correctpass")
        self.assertEqual(user, self.user)

    def test_wrong_password_raises(self):
        with self.assertRaises(InvalidCredentialsError):
            authenticate_user("auth@example.com", "wrongpass")

    def test_wrong_email_raises(self):
        with self.assertRaises(InvalidCredentialsError):
            authenticate_user("nobody@example.com", "correctpass")


class GenerateTokensTests(TestCase):
    def test_returns_access_and_refresh(self):
        user = User.objects.create_user(
            email="tokens@example.com",
            password="testpass123",
        )
        tokens = generate_tokens(user)
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)
        self.assertTrue(len(tokens["access"]) > 10)
        self.assertTrue(len(tokens["refresh"]) > 10)


class ChangePasswordTests(TestCase):
    def test_change_password_success(self):
        user = User.objects.create_user(
            email="changepw@example.com",
            password="oldpass123",
        )
        change_password(user, "oldpass123", "newpass456")
        self.assertTrue(user.check_password("newpass456"))

    def test_change_password_wrong_old_raises(self):
        user = User.objects.create_user(
            email="changepw2@example.com",
            password="oldpass123",
        )
        with self.assertRaises(InvalidCredentialsError):
            change_password(user, "wrongold", "newpass456")
