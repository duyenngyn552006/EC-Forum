from django.contrib import admin

from .models import Comment, Like, SavedItem


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "content_type", "object_id", "status", "created_at")
    list_filter = ("status", "content_type")
    search_fields = ("body", "author__email")


admin.site.register(Like)
admin.site.register(SavedItem)
