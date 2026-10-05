from django.contrib import admin

from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ("query", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("query", "user__email")
