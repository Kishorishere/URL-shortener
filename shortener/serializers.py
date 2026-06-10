import re

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from shortener.models import APIKey, ClickEvent, Domain, ShortenedURL, Tag
from shortener.services.shortcode import generate_short_code, slugify_title, validate_custom_slug
from shortener.services.cleaner import normalize_url

UTM_FIELDS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]
        read_only_fields = ["id"]


class ShortenedURLSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        source="tags",
        many=True,
        write_only=True,
        required=False,
    )
    short_url = serializers.SerializerMethodField()

    class Meta:
        model = ShortenedURL
        fields = [
            "id",
            "short_code",
            "custom_slug",
            "short_url",
            "original_url",
            "title",
            "click_count",
            "is_active",
            "is_expired",
            "show_preview",
            "tags",
            "tag_ids",
            "created_at",
            "updated_at",
            "expires_at",
        ]
        read_only_fields = [
            "id", "short_code", "click_count", "is_active",
            "created_at", "updated_at",
        ]

    def get_short_url(self, obj):
        return f"{settings.BASE_URL}/{obj.active_code}"

    def validate_original_url(self, value):
        if not value:
            raise serializers.ValidationError("URL is required.")
        if len(value) > 2048:
            raise serializers.ValidationError("URL must not exceed 2048 characters.")
        return normalize_url(value)

    def validate_title(self, value):
        value = value.strip()
        if len(value) > 255:
            raise serializers.ValidationError("Title must not exceed 255 characters.")
        return value

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future.")
        return value


class ShortenedURLCreateSerializer(serializers.ModelSerializer):
    custom_slug = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = ShortenedURL
        fields = [
            "original_url", "custom_slug", "title",
            "expires_at", "password", "show_preview",
            *UTM_FIELDS, "tag_ids",
        ]

    def validate_custom_slug(self, value):
        if not value:
            return ""
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Custom slug must be at least 3 characters.")
        error = validate_custom_slug(value)
        if error:
            raise serializers.ValidationError(error)
        return value.lower()

    def validate_original_url(self, value):
        if not value:
            raise serializers.ValidationError("URL is required.")
        if len(value) > 2048:
            raise serializers.ValidationError("URL must not exceed 2048 characters.")
        return normalize_url(value)

    def validate_title(self, value):
        value = value.strip()
        if len(value) > 255:
            raise serializers.ValidationError("Title must not exceed 255 characters.")
        return value

    def validate_password(self, value):
        if value and len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters.")
        if value and len(value) > 128:
            raise serializers.ValidationError("Password must not exceed 128 characters.")
        return value

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future.")
        return value

    def validate(self, attrs):
        for field in UTM_FIELDS:
            val = attrs.get(field, "")
            if val:
                attrs[field] = val.strip()[:100]
        return attrs

    def create(self, validated_data):
        tag_ids = validated_data.pop("tag_ids", [])
        password = validated_data.pop("password", "")
        validated_data["short_code"] = generate_short_code()
        if not validated_data.get("custom_slug") and validated_data.get("title"):
            validated_data["custom_slug"] = slugify_title(validated_data["title"])
        url = ShortenedURL.objects.create(**validated_data)
        if password:
            url.set_password(password)
            url.save(update_fields=["password"])
        if tag_ids:
            url.tags.set(tag_ids)
        return url


class ClickEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickEvent
        fields = [
            "id", "clicked_at", "ip_address", "country",
            "browser", "os", "device_type", "referer_domain",
        ]
        read_only_fields = fields


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ["id", "name", "key", "is_active", "created_at", "last_used_at"]
        read_only_fields = ["id", "key", "created_at", "last_used_at"]


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["id", "domain", "is_verified", "verification_token", "created_at"]
        read_only_fields = ["id", "is_verified", "verification_token", "created_at"]

    def validate_domain(self, value):
        value = value.strip().lower()
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$', value):
            raise serializers.ValidationError("Enter a valid domain name.")
        return value
