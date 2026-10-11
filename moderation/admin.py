from django.contrib import admin

from .models import AccountAppeal, ModerationLog, Report, SensitiveKeyword


@admin.register(SensitiveKeyword)
class SensitiveKeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("keyword",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "content_type", "object_id", "status", "created_at")
    list_filter = ("status", "content_type")


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ("id", "actor", "action", "target_user", "created_at")
    list_filter = ("action",)
    readonly_fields = [f.name for f in ModerationLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AccountAppeal)
class AccountAppealAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at", "reviewed_by")
    list_filter = ("status",)
