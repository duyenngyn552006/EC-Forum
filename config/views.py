from django.db.models import Count, F, Q
from django.shortcuts import render
from django.utils import timezone

from interactions.utils import annotate_interaction_counts

from .mixins import ContentStatus


def _monthly_leaderboard():
    """BXH thanh vien tuong tac nhieu nhat THANG NAY - tinh diem = so bai dang dien dan
    + so binh luan (tren moi loai noi dung) da dang trong thang, chi tinh user active."""
    from accounts.models import User

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return (
        User.objects.filter(is_active=True)
        .annotate(
            post_count=Count(
                "forum_posts",
                filter=Q(forum_posts__status=ContentStatus.PUBLISHED, forum_posts__created_at__gte=month_start),
                distinct=True,
            ),
            comment_count=Count(
                "comments",
                filter=Q(comments__status="published", comments__created_at__gte=month_start),
                distinct=True,
            ),
        )
        .annotate(total_score=F("post_count") + F("comment_count"))
        .filter(total_score__gt=0)
        .order_by("-total_score")[:5]
    )


def _group_leaderboard():
    """BXH nhom hoat dong soi noi nhat THANG NAY - tinh theo so bai dang trong nhom
    (da duyet, published) trong thang, chi tinh nhom dang active."""
    from groups.models import Group

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return (
        Group.objects.filter(status=Group.Status.ACTIVE)
        .annotate(
            post_count=Count(
                "posts",
                filter=Q(posts__status=ContentStatus.PUBLISHED, posts__created_at__gte=month_start),
                distinct=True,
            ),
            member_count=Count("memberships", distinct=True),
        )
        .filter(post_count__gt=0)
        .order_by("-post_count")[:5]
    )


def _top_discussed_posts():
    """Bai viet dien dan co do thao luan soi noi nhat - xep hang theo so binh luan."""
    from forum.models import ForumPost

    return annotate_interaction_counts(
        ForumPost.objects.filter(status=ContentStatus.PUBLISHED).select_related("author", "category"), ForumPost,
    ).filter(comment_count__gt=0).order_by("-comment_count")[:5]


def home_view(request):
    """Trang chu bo cuc 2 cot ty le 7:3 - trai la Thong bao cua Khoa (danh sach day du,
    giong trang announcements:list), phai la Bai viet dien dan sap xep theo luot xem
    cao nhat (trending). KHONG gop Bai dang trong nhom vi do la pham vi noi bo nhom."""
    from announcements.models import Announcement
    from forum.models import ForumPost

    announcements = annotate_interaction_counts(
        Announcement.objects.filter(status=ContentStatus.PUBLISHED).select_related("author"), Announcement,
    ).order_by("-is_pinned", "-created_at")[:3]

    trending_posts = ForumPost.objects.filter(
        status=ContentStatus.PUBLISHED
    ).select_related("author", "category").order_by("-view_count", "-created_at")[:5]

    return render(
        request, "home.html",
        {
            "announcements": announcements, "trending_posts": trending_posts,
            "top_discussed_posts": _top_discussed_posts(),
            "group_leaderboard": _group_leaderboard(),
            "leaderboard": _monthly_leaderboard(),
        },
    )
