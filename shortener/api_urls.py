from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r"links", api_views.ShortenedURLViewSet, basename="api-link")
router.register(r"tags", api_views.TagViewSet, basename="api-tag")
router.register(r"api-keys", api_views.APIKeyViewSet, basename="api-apikey")
router.register(r"domains", api_views.DomainViewSet, basename="api-domain")

urlpatterns = [
    path("bulk/", api_views.bulk_create_api, name="api-bulk"),
]

urlpatterns += router.urls
