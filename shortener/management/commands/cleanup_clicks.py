from django.core.management.base import BaseCommand
from django.utils import timezone

from shortener.models import ClickEvent


class Command(BaseCommand):
    help = "Deletes click events older than the specified retention period"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Retention period in days (default: 365)",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(days=options["days"])
        deleted, _ = ClickEvent.objects.filter(
            clicked_at__lt=cutoff
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} click events older than {options['days']} days")
        )
