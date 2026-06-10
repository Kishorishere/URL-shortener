from django.urls import path

from . import views

app_name = "shortener"

urlpatterns = [
    path("", views.dashboard_list, name="dashboard_list"),
    path("create/", views.dashboard_create, name="dashboard_create"),
    path("bulk/", views.dashboard_bulk, name="dashboard_bulk"),
    path("trash/", views.dashboard_trash, name="dashboard_trash"),
    path("<str:code>/", views.dashboard_detail, name="dashboard_detail"),
    path("<str:code>/edit/", views.dashboard_edit, name="dashboard_edit"),
    path("<str:code>/delete/", views.dashboard_delete, name="dashboard_delete"),
    path("<str:code>/restore/", views.dashboard_restore, name="dashboard_restore"),
    path(
        "<str:code>/qr/<str:format>/",
        views.qr_download,
        name="qr_download",
    ),
]
