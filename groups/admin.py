from django.contrib import admin

from .models import Group, GroupMembership, GroupPost, GroupPostEditHistory


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_by", "approved_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "description", "created_by__email")
    inlines = [GroupMembershipInline]


@admin.register(GroupPost)
class GroupPostAdmin(admin.ModelAdmin):
    list_display = ("title", "group", "author", "status", "edit_count", "created_at")
    list_filter = ("status", "group")
    search_fields = ("title", "body")


admin.site.register(GroupMembership)
admin.site.register(GroupPostEditHistory)
