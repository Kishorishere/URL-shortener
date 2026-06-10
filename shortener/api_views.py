import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from shortener.authentication import APIKeyAuthentication
from shortener.models import APIKey, ClickEvent, Domain, ShortenedURL, Tag
from shortener.serializers import (
    APIKeySerializer,
    ClickEventSerializer,
    DomainSerializer,
    ShortenedURLCreateSerializer,
    ShortenedURLSerializer,
    TagSerializer,
)
from shortener.services.bulk import process_bulk_csv
from shortener.services.qr import generate_qr_base64, generate_qr_svg
from shortener.services.shortcode import generate_short_code

logger = logging.getLogger(__name__)


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ShortenedURLViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_serializer_class(self):
        if self.action == "create":
            return ShortenedURLCreateSerializer
        return ShortenedURLSerializer

    def get_queryset(self):
        qs = ShortenedURL.objects.filter(
            user=self.request.user,
            deleted_at__isnull=True,
        ).select_related("domain").prefetch_related("tags")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(
                Q(original_url__icontains=q)
                | Q(short_code__icontains=q)
                | Q(title__icontains=q)
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def clicks(self, request, pk=None):
        url = self.get_object()
        events = url.click_events.order_by("-clicked_at")[:100]
        serializer = ClickEventSerializer(events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def qr(self, request, pk=None):
        url = self.get_object()
        full_url = request.build_absolute_uri(f"/{url.active_code}")
        fmt = request.query_params.get("format", "png")
        if fmt == "svg":
            svg = generate_qr_svg(full_url)
            return Response({"qr_svg": svg.decode()})
        png = generate_qr_base64(full_url)
        return Response({"qr_png": png})

    @action(detail=True, methods=["post"])
    def soft_delete(self, request, pk=None):
        url = self.get_object()
        url.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class APIKeyViewSet(viewsets.ModelViewSet):
    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        key_obj = APIKey.generate(
            self.request.user,
            serializer.validated_data["name"],
        )
        serializer.instance = key_obj


class DomainViewSet(viewsets.ModelViewSet):
    serializer_class = DomainSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Domain.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        from shortener.services.domain_verifier import generate_verification_token
        serializer.save(
            user=self.request.user,
            verification_token=generate_verification_token(),
        )


@api_view(["post"])
@permission_classes([permissions.IsAuthenticated])
def bulk_create_api(request):
    file = request.FILES.get("file")
    if not file:
        return Response(
            {"error": "No file provided."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        successes, errors = process_bulk_csv(request.user, file)
        return Response({
            "successes": successes,
            "errors": errors,
        })
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
