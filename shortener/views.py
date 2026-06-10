import csv
import io
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth.hashers import check_password

from shortener.forms import BulkUploadForm, ShortenedURLForm
from shortener.models import APIKey, ShortenedURL
from shortener.services.analytics import (
    get_clicks_by_country,
    get_clicks_by_device,
    get_clicks_over_time,
    log_click,
)
from shortener.services.bulk import process_bulk_csv
from shortener.services.qr import generate_qr_base64, generate_qr_svg
from shortener.services.redirect import build_redirect_url, resolve_short_code

logger = logging.getLogger(__name__)


def redirect_view(request, code):
    url = resolve_short_code(code)
    if not url:
        return render(request, "shortener/404.html", status=404)
    if url.is_expired:
        return render(request, "shortener/expired.html", status=410)
    if url.is_password_protected:
        if not request.session.get(f"unlocked_{url.id}"):
            return redirect("password_gate", code=code)
    log_click(url, request)
    if url.show_preview:
        return render(request, "shortener/preview.html", {"url": url})
    destination = build_redirect_url(url)
    response = redirect(destination, permanent=False)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def password_gate_view(request, code):
    url = resolve_short_code(code)
    if not url:
        return render(request, "shortener/404.html", status=404)
    if not url.is_password_protected:
        return redirect("redirect", code=code)
    error = None
    if request.method == "POST":
        entered = request.POST.get("password", "")
        if check_password(entered, url.password):
            request.session[f"unlocked_{url.id}"] = True
            return redirect("redirect", code=code)
        error = "Incorrect password."
    return render(request, "shortener/password_gate.html", {
        "error": error,
        "code": code,
    })


@login_required
def dashboard_list(request):
    urls = ShortenedURL.objects.filter(
        user=request.user, deleted_at__isnull=True
    ).select_related("domain").prefetch_related("tags")
    paginator = Paginator(urls, 25)
    page = request.GET.get("page", 1)
    urls_page = paginator.get_page(page)
    return render(request, "shortener/list.html", {
        "urls": urls_page,
        "paginator": paginator,
        "base_url": settings.BASE_URL,
    })


@login_required
def dashboard_create(request):
    if request.method == "POST":
        form = ShortenedURLForm(request.POST, user=request.user)
        if form.is_valid():
            url = form.save(commit=False)
            url.user = request.user
            url.save()
            form._save_m2m()
            messages.success(request, "Short URL created!")
            return redirect("shortener:dashboard_list")
    else:
        form = ShortenedURLForm(user=request.user)
    return render(request, "shortener/form.html", {
        "form": form,
        "title": "Create Short URL",
        "utm_fields": ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"],
    })


@login_required
def dashboard_edit(request, code):
    url = get_object_or_404(
        ShortenedURL,
        Q(short_code=code) | Q(custom_slug=code),
        user=request.user,
        deleted_at__isnull=True,
    )
    if request.method == "POST":
        form = ShortenedURLForm(
            request.POST, instance=url, user=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Short URL updated!")
            return redirect("shortener:dashboard_detail", code=url.active_code)
    else:
        form = ShortenedURLForm(instance=url, user=request.user)
    return render(request, "shortener/form.html", {
        "form": form,
        "title": "Edit Short URL",
        "url": url,
        "utm_fields": ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"],
    })


@login_required
def dashboard_detail(request, code):
    url = get_object_or_404(
        ShortenedURL,
        Q(short_code=code) | Q(custom_slug=code),
        user=request.user,
        deleted_at__isnull=True,
    )
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    clicks_over_time = get_clicks_over_time(url)
    by_country = get_clicks_by_country(url)
    by_device = get_clicks_by_device(url)
    total_clicks_30d = url.click_events.filter(
        clicked_at__gte=thirty_days_ago
    ).count()
    qr_png = generate_qr_base64(
        f"{settings.BASE_URL}/{url.active_code}"
    )
    clicks_over_time_list = list(clicks_over_time)
    max_click_count = max(
        (item["count"] for item in clicks_over_time_list),
        default=0,
    )
    return render(request, "shortener/detail.html", {
        "url": url,
        "clicks_over_time": clicks_over_time_list,
        "max_click_count": max_click_count,
        "by_country": list(by_country),
        "by_device": list(by_device),
        "total_clicks_30d": total_clicks_30d,
        "short_url": f"{settings.BASE_URL}/{url.active_code}",
        "qr_png": qr_png,
    })


@login_required
def dashboard_delete(request, code):
    url = get_object_or_404(
        ShortenedURL,
        Q(short_code=code) | Q(custom_slug=code),
        user=request.user,
        deleted_at__isnull=True,
    )
    if request.method == "POST":
        url.soft_delete()
        messages.success(request, "Short URL moved to trash.")
        return redirect("shortener:dashboard_list")
    return render(request, "shortener/confirm_delete.html", {"url": url})


@login_required
def dashboard_bulk(request):
    if request.method == "POST":
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                successes, errors = process_bulk_csv(
                    request.user, request.FILES["csv_file"]
                )
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = (
                    "attachment; filename=bulk_results.csv"
                )
                writer = csv.writer(response)
                writer.writerow(["original", "short_code", "error"])
                for s in successes:
                    writer.writerow([s["original"], s["short_code"], ""])
                for e in errors:
                    writer.writerow([e["original"], "", e["error"]])
                return response
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = BulkUploadForm()
    return render(request, "shortener/bulk.html", {"form": form})


@login_required
def dashboard_trash(request):
    urls = ShortenedURL.objects.filter(
        user=request.user,
        deleted_at__isnull=False,
    ).order_by("-deleted_at")
    recovery_window = timezone.now() - timezone.timedelta(days=30)
    return render(request, "shortener/trash.html", {
        "urls": urls,
        "recovery_window": recovery_window,
        "base_url": settings.BASE_URL,
    })


@login_required
def dashboard_restore(request, code):
    url = get_object_or_404(
        ShortenedURL,
        Q(short_code=code) | Q(custom_slug=code),
        user=request.user,
        deleted_at__isnull=False,
    )
    if request.method == "POST":
        url.restore()
        messages.success(request, "Short URL restored.")
        return redirect("shortener:dashboard_list")
    return render(request, "shortener/confirm_restore.html", {"url": url})


@login_required
def qr_download(request, code, format="png"):
    url = get_object_or_404(
        ShortenedURL,
        Q(short_code=code) | Q(custom_slug=code),
        user=request.user,
        deleted_at__isnull=True,
    )
    full_url = f"{settings.BASE_URL}/{url.active_code}"
    if format == "svg":
        svg_bytes = generate_qr_svg(full_url)
        return HttpResponse(svg_bytes, content_type="image/svg+xml")
    qr_png = generate_qr_base64(full_url)
    import base64
    png_bytes = base64.b64decode(qr_png)
    return HttpResponse(png_bytes, content_type="image/png")


if settings.DEBUG:
    from accounts.services import get_stored_otp as _get_stored_otp

    @require_http_methods(["GET"])
    def debug_otp_view(request):
        email = request.GET.get("email", "")
        otp = _get_stored_otp(email)
        return JsonResponse({"email": email, "otp": otp})
