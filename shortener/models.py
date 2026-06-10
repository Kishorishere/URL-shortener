import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils import timezone


class Tag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#6366f1")

    class Meta:
        db_table = "shortener_tag"
        unique_together = ["user", "name"]
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return f"{self.name} ({self.user.email})"


class Domain(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    domain = models.CharField(max_length=253, unique=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shortener_domain"
        verbose_name = "Domain"
        verbose_name_plural = "Domains"

    def __str__(self):
        return self.domain


class ShortenedURL(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shortened_urls",
    )
    original_url = models.URLField(max_length=2048)
    short_code = models.CharField(max_length=20, unique=True, db_index=True)
    custom_slug = models.CharField(max_length=50, unique=True, null=True, blank=True)
    domain = models.ForeignKey(
        Domain,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="urls",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="urls")
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    password = models.CharField(max_length=255, blank=True)
    show_preview = models.BooleanField(default=False)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    utm_term = models.CharField(max_length=100, blank=True)
    utm_content = models.CharField(max_length=100, blank=True)
    click_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "shortener_url"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["short_code"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["deleted_at"]),
        ]
        verbose_name = "Shortened URL"
        verbose_name_plural = "Shortened URLs"

    @property
    def active_code(self):
        return self.custom_slug or self.short_code

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_password_protected(self):
        return bool(self.password)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    def restore(self):
        self.is_active = True
        self.deleted_at = None
        self.save(update_fields=["is_active", "deleted_at"])

    def __str__(self):
        return f"{self.active_code} -> {self.original_url[:50]}"


class ClickEvent(models.Model):
    url = models.ForeignKey(
        ShortenedURL,
        on_delete=models.CASCADE,
        related_name="click_events",
    )
    clicked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField(blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    device_type = models.CharField(
        max_length=10,
        choices=[
            ("desktop", "Desktop"),
            ("mobile", "Mobile"),
            ("tablet", "Tablet"),
        ],
        blank=True,
    )
    referer = models.URLField(max_length=2048, blank=True)
    referer_domain = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "shortener_click"
        indexes = [
            models.Index(fields=["url", "clicked_at"]),
            models.Index(fields=["url", "country"]),
            models.Index(fields=["url", "device_type"]),
        ]
        verbose_name = "Click Event"
        verbose_name_plural = "Click Events"

    def __str__(self):
        return f"{self.url.active_code} @ {self.clicked_at}"


class APIKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "shortener_apikey"
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    @classmethod
    def generate(cls, user, name):
        key = secrets.token_urlsafe(32)
        return cls.objects.create(user=user, name=name, key=key)
