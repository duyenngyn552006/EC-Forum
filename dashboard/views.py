from datetime import timedelta

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from announcements.models import Announcement
from config.mixins import ContentStatus
from forum.models import ForumPost
from groups.models import Group
from interactions.models import Comment, Like
from moderation.models import Report


def _can_view_dashboard(user):
    # Chi Giao vu Khoa duoc xem thong ke dien dan (da chot voi nhom, khac voi de xuat
    # ban dau trong CLAUDE.md la ca BCN Khoa cung xem duoc)
    return user.is_authenticated and user.role == User.Role.STAFF


@user_passes_test(_can_view_dashboard, login_url="home")
def overview(request):
    last_7_days = timezone.now() - timedelta(days=7)

    context = {
        "total_users": User.objects.count(),
        "users_by_role": User.objects.values("role").order_by("role").annotate(count=Count("id")),
        "total_forum_posts": ForumPost.objects.filter(status=ContentStatus.PUBLISHED).count(),
        "total_announcements": Announcement.objects.filter(status=ContentStatus.PUBLISHED).count(),
        "total_groups": Group.objects.filter(status=Group.Status.ACTIVE).count(),
        "pending_groups": Group.objects.filter(status=Group.Status.PENDING).count(),
        "total_comments": Comment.objects.filter(status=Comment.Status.PUBLISHED).count(),
        "total_likes": Like.objects.count(),
        "pending_reports": Report.objects.filter(status=Report.Status.PENDING).count(),
        "new_posts_last_7_days": ForumPost.objects.filter(created_at__gte=last_7_days).count(),
        "new_users_last_7_days": User.objects.filter(date_joined__gte=last_7_days).count(),
    }
    return render(request, "dashboard/overview.html", context)
