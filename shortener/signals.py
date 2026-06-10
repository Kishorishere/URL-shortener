import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from shortener.cache import invalidate_url_cache
from shortener.models import APIKey, ShortenedURL

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=ShortenedURL)
def on_url_change(sender, instance, **kwargs):
    if instance.short_code:
        invalidate_url_cache(instance.short_code)
    if instance.custom_slug:
        invalidate_url_cache(instance.custom_slug)


@receiver(post_save, sender=APIKey)
def on_apikey_created(sender, instance, created, **kwargs):
    if created:
        logger.info("API key created for user %s: %s", instance.user.email, instance.name)
