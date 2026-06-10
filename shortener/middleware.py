from django.shortcuts import get_object_or_404

from shortener.models import Domain


class CustomDomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0]
        try:
            domain = Domain.objects.get(domain=host, is_verified=True)
            request.custom_domain = domain
        except Domain.DoesNotExist:
            request.custom_domain = None
        return self.get_response(request)
