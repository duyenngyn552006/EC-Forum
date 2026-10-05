from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from moderation.services import find_sensitive_keyword, log_action
from notifications.models import Notification
from notifications.services import notify

from .models import Comment, Like, SavedItem
from .utils import resolve_target


def _content_owner(obj):
    return getattr(obj, "author", None) or getattr(obj, "created_by", None)


def _can_manage_comment(user, comment):
    return user.is_authenticated and (user == comment.author or user.role == "staff")


@login_required
@require_POST
@ratelimit(key="user", rate="20/m", block=True)
def add_comment(request, model_key, object_id):
    content_type, obj = resolve_target(model_key, object_id)
    body = request.POST.get("body", "").strip()
    parent_id = request.POST.get("parent_id") or None

    if not body:
        messages.error(request, "Nội dung bình luận không được để trống.")
        return redirect(obj.get_absolute_url())

    keyword = find_sensitive_keyword(body)
    status = Comment.Status.PENDING_REVIEW if keyword else Comment.Status.PUBLISHED

    comment = Comment.objects.create(
        author=request.user, content_type=content_type, object_id=obj.pk,
        parent_id=parent_id, body=body, status=status,
    )
    if keyword:
        log_action(
            actor=None, action="warn",
            reason=f"Bình luận tự động chuyển chờ kiểm duyệt do từ khóa: '{keyword.keyword}'",
            content_object=comment,
        )
        messages.warning(request, "Bình luận chứa từ khóa nhạy cảm nên đang chờ kiểm duyệt.")
    else:
        messages.success(request, "Đã gửi bình luận.")

    owner = _content_owner(obj)
    if owner and owner != request.user:
        notify(
            recipient=owner, verb=Notification.Verb.COMMENT, actor=request.user,
            message="Có bình luận mới trên nội dung của bạn.", content_object=obj,
        )

    if comment.parent_id and comment.parent.author != request.user and comment.parent.author != owner:
        notify(
            recipient=comment.parent.author, verb=Notification.Verb.COMMENT, actor=request.user,
            message="Đã trả lời bình luận của bạn.", content_object=obj,
        )

    mentioned_ids = [int(v) for v in request.POST.getlist("mentioned_user_ids") if v.isdigit()]
    if mentioned_ids:
        from groups.mentions import notify_mentions

        notify_mentions(request.user, mentioned_ids, comment)
    return redirect(obj.get_absolute_url())


@login_required
@require_POST
def edit_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if not _can_manage_comment(request.user, comment):
        messages.error(request, "Bạn không có quyền sửa bình luận này.")
        return redirect(comment.content_object.get_absolute_url())

    body = request.POST.get("body", "").strip()
    if not body:
        messages.error(request, "Nội dung bình luận không được để trống.")
        return redirect(comment.content_object.get_absolute_url())

    keyword = find_sensitive_keyword(body)
    comment.body = body
    comment.status = Comment.Status.PENDING_REVIEW if keyword else Comment.Status.PUBLISHED
    comment.is_edited = True
    comment.save(update_fields=["body", "status", "is_edited", "updated_at"])
    if keyword:
        log_action(
            actor=None, action="warn",
            reason=f"Bình luận tự động chuyển chờ kiểm duyệt do từ khóa: '{keyword.keyword}'",
            content_object=comment,
        )
        messages.warning(request, "Bình luận chứa từ khóa nhạy cảm nên đang chờ kiểm duyệt.")
    else:
        messages.success(request, "Đã cập nhật bình luận.")
    return redirect(comment.content_object.get_absolute_url())


@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if not _can_manage_comment(request.user, comment):
        messages.error(request, "Bạn không có quyền xóa bình luận này.")
        return redirect(comment.content_object.get_absolute_url())

    obj = comment.content_object
    comment.delete()
    messages.success(request, "Đã xóa bình luận.")
    return redirect(obj.get_absolute_url())


@login_required
@require_POST
def toggle_like(request, model_key, object_id):
    content_type, obj = resolve_target(model_key, object_id)
    like, created = Like.objects.get_or_create(user=request.user, content_type=content_type, object_id=obj.pk)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        owner = _content_owner(obj)
        if owner and owner != request.user:
            notify(
                recipient=owner, verb=Notification.Verb.LIKE, actor=request.user,
                message="Có lượt thích mới trên nội dung của bạn.", content_object=obj,
            )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        count = Like.objects.filter(content_type=content_type, object_id=obj.pk).count()
        return JsonResponse({"liked": liked, "count": count})
    return redirect(obj.get_absolute_url())


@login_required
@require_POST
def toggle_save(request, model_key, object_id):
    content_type, obj = resolve_target(model_key, object_id)
    saved_item, created = SavedItem.objects.get_or_create(user=request.user, content_type=content_type, object_id=obj.pk)
    if not created:
        saved_item.delete()
        messages.success(request, "Đã bỏ lưu.")
    else:
        messages.success(request, "Đã lưu bài viết.")

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"saved": created})
    return redirect(obj.get_absolute_url())
