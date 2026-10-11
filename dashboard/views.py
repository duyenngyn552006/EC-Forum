from urllib.parse import urlencode

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Min
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from announcements.models import Announcement
from config.mixins import ContentStatus
from forum.models import ForumPost
from groups.models import Group
from interactions.models import Comment, Like
from moderation.models import Report

from . import stats


def _can_view_dashboard(user):
    # Chi Giao vu Khoa duoc xem thong ke dien dan (da chot voi nhom, khac voi de xuat
    # ban dau trong CLAUDE.md la ca BCN Khoa cung xem duoc)
    return user.is_authenticated and user.role == User.Role.STAFF


def _users_by_role():
    counts = dict(User.objects.values_list("role").annotate(count=Count("id")))
    return [{"label": label, "count": counts.get(value, 0)} for value, label in User.Role.choices]


# (khoa, nhan, queryset, truong thoi gian, so tong cong don) - thu tu = thu tu o so lieu tren dashboard
def _metric_sources():
    published_comments = Comment.objects.filter(status=Comment.Status.PUBLISHED)
    return [
        ("users", "Người dùng mới", User.objects.all(), "date_joined", User.objects.count()),
        ("posts", "Bài viết diễn đàn", ForumPost.objects.all(), "created_at",
         ForumPost.objects.filter(status=ContentStatus.PUBLISHED).count()),
        ("comments", "Bình luận", published_comments, "created_at", published_comments.count()),
        ("reactions", "Lượt cảm xúc", Like.objects.all(), "created_at", Like.objects.count()),
        ("announcements", "Thông báo", Announcement.objects.all(), "created_at",
         Announcement.objects.filter(status=ContentStatus.PUBLISHED).count()),
        ("groups", "Nhóm mới", Group.objects.all(), "created_at", Group.objects.filter(status=Group.Status.ACTIVE).count()),
    ]


# Bieu do hoat dong: 3 chuoi (gioi han 3 mau dau cua bang mau - xem dataviz: qua 3 chuoi khong con phan biet an toan)
CHART_SERIES = ("posts", "comments", "users")


def _year_options(today, viewing_year):
    """Cac nam co the chon: tu nam co du lieu som nhat (tai khoan / bai viet) - hoac nam dang xem neu som hon - den nam nay."""
    first_dates = [
        User.objects.aggregate(first=Min("date_joined"))["first"],
        ForumPost.objects.aggregate(first=Min("created_at"))["first"],
    ]
    years = [timezone.localtime(d).year for d in first_dates if d]
    return list(range(min(years + [today.year, viewing_year]), max(today.year, viewing_year) + 1))


@user_passes_test(_can_view_dashboard, login_url="home")
def overview(request):
    info = stats.resolve_period(request.GET.get("period"), request.GET)
    metrics, series = [], {}
    for key, label, queryset, field, total in _metric_sources():
        current = stats.period_count(queryset, field, info["start"], info["end"])
        previous = stats.period_count(queryset, field, info["prev_start"], info["start"])
        metrics.append({
            "key": key, "label": label, "value": current, "previous": previous, "total": total,
            "delta": stats.delta_percent(current, previous),
        })
        if key in CHART_SERIES:
            series[key] = {"label": label, "values": stats.count_series(queryset, field, info)}

    chart = {
        "labels": [stats.bucket_label(b, info["unit"], info["period"]) for b in info["buckets"]],
        "series": [{"key": k, **series[k]} for k in CHART_SERIES],
    }
    context = {
        "info": info,
        "period": info["period"],
        "period_labels": stats.PERIOD_LABELS,
        "prev_query": urlencode(info["prev_params"]),
        "next_query": urlencode(info["next_params"]) if info["next_params"] else "",
        "year_options": _year_options(info["today"], info["start"].year),
        "month_options": range(1, 13),
        "metrics": metrics,
        "chart": chart,
        "chart_rows": list(zip(chart["labels"], *[s["values"] for s in chart["series"]])),
        "users_by_role": _users_by_role(),
        "pending_groups": Group.objects.filter(status=Group.Status.PENDING).count(),
        "pending_reports": Report.objects.filter(status=Report.Status.PENDING).count(),
    }
    return render(request, "dashboard/overview.html", context)
