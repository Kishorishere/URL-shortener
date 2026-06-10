from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Api-Key "):
            return None
        key = auth_header.split(" ", 1)[1].strip()
        from shortener.models import APIKey
        try:
            api_key = APIKey.objects.select_related("user").get(
                key=key, is_active=True
            )
        except APIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key.")
        APIKey.objects.filter(pk=api_key.pk).update(
            last_used_at=timezone.now()
        )
        return (api_key.user, api_key)
