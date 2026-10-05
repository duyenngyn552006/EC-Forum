from django.contrib import admin

from .models import Category, ForumPost, ForumPostEditHistory, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "max_pinned")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ForumPostEditHistoryInline(admin.TabularInline):
    model = ForumPostEditHistory
    extra = 0
    readonly_fields = ("editor", "title", "body", "edited_at")
    can_delete = False


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "status", "is_pinned", "edit_count", "created_at")
    list_filter = ("status", "is_pinned", "category")
    search_fields = ("title", "body", "author__email")
    inlines = [ForumPostEditHistoryInline]
