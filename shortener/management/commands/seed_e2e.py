from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from shortener.models import ShortenedURL, Tag

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds test data for Playwright E2E tests"

    def handle(self, *args, **options):
        now = timezone.now()

        verified_user, created = User.objects.get_or_create(
            email="e2e-verified@example.com",
            defaults={
                "username": "E2E Verified",
                "is_verified": True,
            },
        )
        if created:
            verified_user.set_password("TestPass123!")
            verified_user.save(update_fields=["password"])

        unverified_user, created = User.objects.get_or_create(
            email="e2e-unverified@example.com",
            defaults={
                "username": "E2E Unverified",
                "is_verified": False,
            },
        )
        if created:
            unverified_user.set_password("TestPass123!")
            unverified_user.save(update_fields=["password"])

        tag1, _ = Tag.objects.get_or_create(
            user=verified_user, name="work", defaults={"color": "#6366f1"}
        )
        tag2, _ = Tag.objects.get_or_create(
            user=verified_user, name="personal", defaults={"color": "#10b981"}
        )

        active_url, created = ShortenedURL.objects.get_or_create(
            short_code="test1",
            defaults={
                "user": verified_user,
                "original_url": "https://example.com/active",
                "title": "Active Link",
                "is_active": True,
            },
        )
        if created:
            active_url.tags.add(tag1)

        password_url, created = ShortenedURL.objects.get_or_create(
            short_code="pwd1",
            defaults={
                "user": verified_user,
                "original_url": "https://example.com/secret",
                "title": "Protected Link",
                "is_active": True,
            },
        )
        if created:
            password_url.set_password("secret123")
            password_url.save(update_fields=["password"])

        preview_url, created = ShortenedURL.objects.get_or_create(
            short_code="prev1",
            defaults={
                "user": verified_user,
                "original_url": "https://example.com/preview",
                "title": "Preview Link",
                "is_active": True,
                "show_preview": True,
            },
        )

        expired_url, created = ShortenedURL.objects.get_or_create(
            short_code="exp1",
            defaults={
                "user": verified_user,
                "original_url": "https://example.com/gone",
                "title": "Expired Link",
                "is_active": True,
                "expires_at": now - timedelta(hours=1),
            },
        )

        deleted_url, created = ShortenedURL.objects.get_or_create(
            short_code="del1",
            defaults={
                "user": verified_user,
                "original_url": "https://example.com/deleted",
                "title": "Deleted Link",
                "is_active": False,
                "deleted_at": now,
            },
        )

        self.stdout.write(self.style.SUCCESS("E2E test data seeded successfully"))
