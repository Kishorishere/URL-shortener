from django.core.management.base import BaseCommand
from django.utils import timezone

from shortener.models import ShortenedURL


class Command(BaseCommand):
    help = "Deactivates expired short URLs"

    def handle(self, *args, **options):
        expired = ShortenedURL.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True,
            deleted_at__isnull=True,
        )
        count = expired.update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(f"Deactivated {count} expired URLs")
        )
