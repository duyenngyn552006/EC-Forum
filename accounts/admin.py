from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("email", "get_full_name", "class_name", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "class_name")
    search_fields = ("email", "username", "first_name", "last_name", "student_id", "class_name")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Thông tin cá nhân", {"fields": ("first_name", "last_name", "student_id", "class_name", "phone", "avatar", "cover_image", "bio")}),
        ("Vai trò & quyền", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Khóa tài khoản", {"fields": ("locked_reason", "locked_at")}),
        ("Thời gian", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "role", "password1", "password2"),
        }),
    )
