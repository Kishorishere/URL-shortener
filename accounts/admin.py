from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "username", "is_verified", "is_staff", "date_joined"]
    list_filter = ["is_verified", "is_staff", "is_active"]
    search_fields = ["email", "username"]
    ordering = ["-date_joined"]

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("phone_number", "avatar", "is_verified")}),
    )
