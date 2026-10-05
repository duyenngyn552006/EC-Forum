from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from announcements.models import Announcement
from config.mixins import ContentStatus
from forum.models import Category, ForumPost
from groups.models import GroupPost

from .services import record_search

MAX_RESULTS = 50

CONTENT_TYPE_CHOICES = (
    ("announcement", "Thông tin / thông báo"),
    ("forum", "Bài diễn đàn"),
    ("group", "Bài trong nhóm"),
)


def _visible_status(user):
    """Nguoi dung thuong chi tim thay noi dung da dang cong khai; rieng Giao vu Khoa
    thay ca noi dung dang cho kiem duyet/da an de phuc vu giam sat toan he thong
    (CLAUDE.md: Giao vu Khoa "giam sat/kiem duyet toan he thong") - tra ve None nghia
    la khong loc theo status (thay tat ca)."""
    if user.is_authenticated and user.role == User.Role.STAFF:
        return None
    return ContentStatus.PUBLISHED


def _apply_common_filters(qs, query, author, class_name, date_from, date_to):
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
    if author:
        qs = qs.filter(
            Q(author__email__icontains=author)
            | Q(author__first_name__icontains=author)
            | Q(author__last_name__icontains=author)
        )
    if class_name:
        qs = qs.filter(author__class_name__icontains=class_name)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


def _to_result(obj, type_key, type_label):
    return {
        "object": obj,
        "type_key": type_key,
        "type_label": type_label,
        "author": obj.author,
        "created_at": obj.created_at,
        "is_edited": getattr(obj, "is_edited", False),
        "url": obj.get_absolute_url(),
    }


def search_view(request):
    query = request.GET.get("q", "").strip()
    content_type = request.GET.get("type", "")
    category_slug = request.GET.get("category", "")
    author = request.GET.get("author", "").strip()
    class_name = request.GET.get("class_name", "").strip()
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    status = _visible_status(request.user)
    results = []

    if not content_type or content_type == "announcement":
        qs = Announcement.objects.select_related("author")
        if status:
            qs = qs.filter(status=status)
        qs = _apply_common_filters(qs, query, author, class_name, date_from, date_to)
        results += [_to_result(obj, "announcement", "Thông tin / thông báo") for obj in qs]

    if not content_type or content_type == "forum":
        qs = ForumPost.objects.select_related("author", "category")
        if status:
            qs = qs.filter(status=status)
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        qs = _apply_common_filters(qs, query, author, class_name, date_from, date_to)
        results += [_to_result(obj, "forum", "Bài diễn đàn") for obj in qs]

    if not content_type or content_type == "group":
        qs = GroupPost.objects.select_related("author", "group")
        if status:
            qs = qs.filter(status=status)
        qs = _apply_common_filters(qs, query, author, class_name, date_from, date_to)
        results += [_to_result(obj, "group", "Bài trong nhóm") for obj in qs]

    results.sort(key=lambda r: r["created_at"], reverse=True)
    results = results[:MAX_RESULTS]

    if query:
        record_search(request.user, query)

    paginator = Paginator(results, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    recent_searches = (
        list(request.user.search_history.values_list("query", flat=True)[:10])
        if request.user.is_authenticated
        else []
    )

    querystring_params = request.GET.copy()
    querystring_params.pop("page", None)

    context = {
        "querystring": querystring_params.urlencode(),
        "query": query,
        "content_type": content_type,
        "category_slug": category_slug,
        "author": author,
        "class_name": class_name,
        "date_from": date_from,
        "date_to": date_to,
        "page_obj": page_obj,
        "categories": Category.objects.all(),
        "content_type_choices": CONTENT_TYPE_CHOICES,
        "recent_searches": recent_searches,
        "has_filters": any([query, content_type, category_slug, author, class_name, date_from, date_to]),
    }
    return render(request, "search/search_results.html", context)


@login_required
@require_POST
def clear_search_history(request):
    request.user.search_history.all().delete()
    return redirect("search:results")
