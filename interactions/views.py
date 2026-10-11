from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from moderation.services import find_sensitive_keyword, log_action
from notifications.models import Notification
from notifications.services import notify

from .follows import notify_followers
from .forms import PollForm
from .models import Comment, Follow, Like, Poll, PollOption, PollVote, SavedItem
from .polls import POLLABLE_MODELS, can_create_poll, can_delete_poll, can_vote, get_poll
from .utils import resolve_follow_target, resolve_target


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

    # Chi nhan parent thuoc dung noi dung nay (tranh gan reply vao binh luan cua bai khac)
    parent = None
    if parent_id:
        parent = Comment.objects.filter(pk=parent_id, content_type=content_type, object_id=obj.pk).first()
        if parent is None:
            messages.error(request, "Bình luận bạn trả lời không còn tồn tại.")
            return redirect(obj.get_absolute_url())

    keyword = find_sensitive_keyword(body)
    status = Comment.Status.PENDING_REVIEW if keyword else Comment.Status.PUBLISHED

    comment = Comment.objects.create(
        author=request.user, content_type=content_type, object_id=obj.pk,
        parent=parent, body=body, status=status,
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

    # Nguoi nhan da duoc bao boi thong bao cu the hon thi khong bao them (moi nguoi 1 thong bao / binh luan):
    # tra loi -> REPLY cho chu binh luan goc; chu bai -> COMMENT (tru khi da nhan REPLY); nguoi theo doi bai -> FOLLOW_UPDATE
    owner = _content_owner(obj)
    parent_author = parent.author if parent else None
    already_notified = {request.user.pk}

    if parent_author and parent_author != request.user:
        notify(
            recipient=parent_author, verb=Notification.Verb.REPLY, actor=request.user,
            message=f"{request.user} đã trả lời bình luận của bạn.", content_object=obj,
        )
        already_notified.add(parent_author.pk)

    if owner and owner.pk not in already_notified:
        notify(
            recipient=owner, verb=Notification.Verb.COMMENT, actor=request.user,
            message="Có bình luận mới trên nội dung của bạn.", content_object=obj,
        )
        already_notified.add(owner.pk)

    # Binh luan cho kiem duyet chua hien thi cong khai nen khong bao nguoi theo doi
    if status == Comment.Status.PUBLISHED:
        notify_followers(
            [obj], f"Có bình luận mới trong bài bạn theo dõi: {obj}", obj, exclude_user_ids=already_notified,
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
    """Tha/doi/go cam xuc: bam lai dung cam xuc dang chon = go; chon cam xuc khac = doi
    (moi user 1 cam xuc / noi dung). Khong co `reaction` trong POST -> mac dinh "Thich"."""
    content_type, obj = resolve_target(model_key, object_id)
    reaction = request.POST.get("reaction", Like.Reaction.LIKE)
    if reaction not in Like.Reaction.values:
        reaction = Like.Reaction.LIKE

    like = Like.objects.filter(user=request.user, content_type=content_type, object_id=obj.pk).first()
    if like is None:
        Like.objects.create(user=request.user, content_type=content_type, object_id=obj.pk, reaction=reaction)
        liked = True
        owner = _content_owner(obj)
        if owner and owner != request.user:
            notify(
                recipient=owner, verb=Notification.Verb.LIKE, actor=request.user,
                message="Có lượt thích mới trên nội dung của bạn.", content_object=obj,
            )
    elif like.reaction == reaction:
        like.delete()
        liked = False
        reaction = None
    else:
        like.reaction = reaction
        like.save(update_fields=["reaction"])
        liked = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        count = Like.objects.filter(content_type=content_type, object_id=obj.pk).count()
        return JsonResponse({"liked": liked, "count": count, "reaction": reaction})
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


def _poll_target(model_key, object_id):
    """Poll chi gan duoc vao bai dien dan/bai nhom."""
    if model_key not in POLLABLE_MODELS:
        raise Http404("Loại nội dung không hỗ trợ bình chọn.")
    return resolve_target(model_key, object_id)


@login_required
@ratelimit(key="user", rate="10/m", block=True)
def poll_create(request, model_key, object_id):
    """Tao binh chon cho 1 bai. Noi dung (cau hoi + lua chon) van quet tu khoa nhay cam:
    poll khong co trang thai cho duyet nen neu vi pham thi tu choi tao va bao ly do."""
    content_type, obj = _poll_target(model_key, object_id)
    if not can_create_poll(request.user, obj):
        messages.error(request, "Bạn không có quyền tạo bình chọn cho bài viết này.")
        return redirect(obj.get_absolute_url())
    if get_poll(obj) is not None:
        messages.error(request, "Bài viết này đã có bình chọn.")
        return redirect(obj.get_absolute_url())

    if request.method == "POST":
        form = PollForm(request.POST)
        if form.is_valid():
            question = form.cleaned_data["question"]
            options = form.cleaned_data["options"]
            keyword = find_sensitive_keyword(question, *options)
            if keyword:
                form.add_error(None, f"Nội dung bình chọn chứa từ khóa nhạy cảm ('{keyword.keyword}'). Vui lòng chỉnh sửa.")
            else:
                poll = Poll.objects.create(
                    content_type=content_type, object_id=obj.pk, question=question,
                    closes_at=form.cleaned_data["closes_at"], created_by=request.user,
                )
                PollOption.objects.bulk_create(
                    [PollOption(poll=poll, text=text, position=i) for i, text in enumerate(options)]
                )
                messages.success(request, "Đã tạo bình chọn.")
                return redirect(obj.get_absolute_url())
    else:
        form = PollForm()
    return render(request, "interactions/poll_form.html", {"form": form, "object": obj})


@login_required
@require_POST
@ratelimit(key="user", rate="30/m", block=True)
def poll_vote(request, poll_id):
    """Binh chon hoac doi lua chon (truoc han chot). Moi nguoi 1 phieu / poll."""
    poll = get_object_or_404(Poll, pk=poll_id)
    target = poll.content_object
    if target is None:
        raise Http404
    if poll.is_closed:
        messages.error(request, "Bình chọn đã kết thúc.")
    elif not can_vote(request.user, poll):
        messages.error(request, "Chỉ thành viên nhóm mới được bình chọn trong bài viết của nhóm.")
    else:
        option = poll.options.filter(pk=request.POST.get("option_id") or 0).first()
        if option is None:
            messages.error(request, "Vui lòng chọn một lựa chọn hợp lệ.")
        else:
            PollVote.objects.update_or_create(poll=poll, user=request.user, defaults={"option": option})
            messages.success(request, "Đã ghi nhận lựa chọn của bạn.")
    return redirect(target.get_absolute_url())


@login_required
@require_POST
def poll_delete(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    target = poll.content_object
    if not can_delete_poll(request.user, poll):
        messages.error(request, "Bạn không có quyền xóa bình chọn này.")
    else:
        poll.delete()
        messages.success(request, "Đã xóa bình chọn.")
    return redirect(target.get_absolute_url() if target is not None else "home")


def _safe_next_url(request, fallback):
    from django.utils.http import url_has_allowed_host_and_scheme

    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return fallback


@login_required
@require_POST
@ratelimit(key="user", rate="30/m", block=True)
def toggle_follow(request, model_key, object_id):
    """Theo doi / bo theo doi chuyen muc, the hoac bai dien dan."""
    content_type, obj = resolve_follow_target(model_key, object_id)
    follow, created = Follow.objects.get_or_create(user=request.user, content_type=content_type, object_id=obj.pk)
    if created:
        messages.success(request, f"Đã theo dõi “{obj}”. Bạn sẽ nhận thông báo khi có cập nhật.")
    else:
        follow.delete()
        messages.success(request, f"Đã bỏ theo dõi “{obj}”.")
    return redirect(_safe_next_url(request, fallback=reverse("interactions:following")))


@login_required
def following_list(request):
    """Danh sach muc dang theo doi cua toi (kem nut bo theo doi)."""
    rows = []
    for follow in request.user.follows.select_related("content_type"):
        target = follow.content_object
        if target is None:
            continue
        kind = follow.content_type.model
        if kind == "category":
            url = reverse("forum:post_list_by_category", args=[target.slug])
        elif kind == "tag":
            url = f"{reverse('forum:post_list')}?tag={target.slug}"
        else:
            url = target.get_absolute_url()
        rows.append({"kind": kind, "label": str(target), "url": url, "model_key": kind, "object_id": target.pk})
    return render(request, "interactions/following_list.html", {"rows": rows})


def _can_download_document(user, target):
    """Bai cong khai: moi user dang nhap. Bai chua cong khai (cho duyet/an): tac gia, Giao vu Khoa,
    hoac truong/pho nhom (bai trong nhom)."""
    if target is None:
        return False
    if getattr(target, "status", "published") == "published":
        return True
    if user == getattr(target, "author", None) or user.role == "staff":
        return True
    if target._meta.model_name == "grouppost":
        from .polls import _is_group_manager

        return _is_group_manager(user, target.group)
    return False


@login_required
def download_document(request, pk):
    """Tai tep dinh kem: luon tai xuong (Content-Disposition: attachment, octet-stream) de tep .html/.svg
    nguy hiem gia dang duoi khac khong bao gio chay tren domain dien dan."""
    import os

    from django.http import FileResponse

    from .models import DocumentLink

    doc = get_object_or_404(DocumentLink, pk=pk)
    if not doc.file or not _can_download_document(request.user, doc.content_object):
        raise Http404("Không tìm thấy tài liệu.")
    ext = os.path.splitext(doc.file.name)[1]
    filename = doc.title if doc.title.lower().endswith(ext.lower()) else f"{doc.title}{ext}"
    try:
        handle = doc.file.open("rb")
    except FileNotFoundError:
        raise Http404("Tệp không còn tồn tại trên máy chủ.")
    return FileResponse(handle, as_attachment=True, filename=filename, content_type="application/octet-stream")
