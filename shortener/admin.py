from django.contrib import admin

from .models import APIKey, ClickEvent, Domain, ShortenedURL, Tag


@admin.register(ShortenedURL)
class ShortenedURLAdmin(admin.ModelAdmin):
    list_display = [
        "short_code",
        "truncated_original",
        "user",
        "click_count",
        "is_active",
        "expires_at",
        "created_at",
    ]
    list_filter = ["is_active", "show_preview", "created_at"]
    search_fields = ["short_code", "custom_slug", "original_url", "user__email"]
    readonly_fields = ["click_count", "created_at", "updated_at", "deleted_at"]
    raw_id_fields = ["user"]

    def truncated_original(self, obj):
        if len(obj.original_url) > 60:
            return obj.original_url[:60] + "..."
        return obj.original_url

    truncated_original.short_description = "Original URL"


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ["url", "clicked_at", "country", "device_type", "browser"]
    list_filter = ["device_type", "country", "clicked_at"]
    readonly_fields = [f.name for f in ClickEvent._meta.fields]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "color"]
    list_filter = ["user"]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["domain", "user", "is_verified", "created_at"]
    list_filter = ["is_verified"]


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "is_active", "last_used_at", "created_at"]
    list_filter = ["is_active"]
