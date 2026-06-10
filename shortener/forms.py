from django import forms
from django.utils import timezone

from shortener.models import ShortenedURL, Tag
from shortener.services.shortcode import generate_short_code, validate_custom_slug
from shortener.services.cleaner import normalize_url

UTM_FIELDS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]


class ShortenedURLForm(forms.ModelForm):
    class Meta:
        model = ShortenedURL
        fields = [
            "original_url",
            "custom_slug",
            "title",
            "tags",
            "expires_at",
            "password",
            "show_preview",
            *UTM_FIELDS,
        ]
        widgets = {
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "password": forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["tags"].queryset = Tag.objects.filter(user=user)
        self.fields["tags"].required = False

    def clean_original_url(self):
        url = self.cleaned_data["original_url"]
        if not url:
            raise forms.ValidationError("URL is required.")
        if len(url) > 2048:
            raise forms.ValidationError("URL must not exceed 2048 characters.")
        return normalize_url(url)

    def clean_custom_slug(self):
        slug = self.cleaned_data.get("custom_slug", "")
        if not slug:
            return ""
        slug = slug.strip()
        if len(slug) < 3:
            raise forms.ValidationError("Custom slug must be at least 3 characters.")
        error = validate_custom_slug(slug)
        if error:
            raise forms.ValidationError(error)
        return slug.lower()

    def clean_title(self):
        value = self.cleaned_data.get("title", "")
        if value:
            value = value.strip()
            if len(value) > 255:
                raise forms.ValidationError("Title must not exceed 255 characters.")
        return value

    def clean_password(self):
        value = self.cleaned_data.get("password", "")
        if value and len(value) < 6:
            raise forms.ValidationError("Password must be at least 6 characters.")
        if value and len(value) > 128:
            raise forms.ValidationError("Password must not exceed 128 characters.")
        return value

    def clean_expires_at(self):
        value = self.cleaned_data.get("expires_at")
        if value and value <= timezone.now():
            raise forms.ValidationError("Expiration date must be in the future.")
        return value

    def clean(self):
        cleaned = super().clean()
        for field in UTM_FIELDS:
            val = cleaned.get(field, "")
            if val:
                cleaned[field] = val.strip()[:100]
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.short_code:
            instance.short_code = generate_short_code()
        if not instance.custom_slug and instance.title:
            from shortener.services.shortcode import slugify_title
            instance.custom_slug = slugify_title(instance.title, exclude_id=instance.pk)
        if self.cleaned_data.get("password"):
            instance.set_password(self.cleaned_data["password"])
        if commit:
            instance.save()
            self._save_m2m()
        return instance


class BulkUploadForm(forms.Form):
    csv_file = forms.FileField()
