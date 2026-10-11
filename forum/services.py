from django.utils import timezone

from config.mixins import ContentStatus, PinLimitExceeded
from config.sanitize import sanitize_html
from interactions.follows import notify_followers
from moderation.services import find_sensitive_keyword, log_action
from notifications.models import Notification
from notifications.services import notify

from .models import ForumPost, ForumPostEditHistory


def pin_post(post: ForumPost, actor):
    """Ghim bai trong pham vi chuyen muc, tu choi neu da dat gioi han (khong tu unpin bai cu)."""
    if post.is_pinned:
        return post
    max_pinned = post.category.get_effective_max_pinned()
    current_pinned = ForumPost.objects.filter(category=post.category, is_pinned=True).count()
    if current_pinned >= max_pinned:
        raise PinLimitExceeded(max_pinned)
    post.is_pinned = True
    post.pinned_at = timezone.now()
    post.pinned_by = actor
    post.save(update_fields=["is_pinned", "pinned_at", "pinned_by"])
    return post


def unpin_post(post: ForumPost, actor):
    post.is_pinned = False
    post.pinned_at = None
    post.pinned_by = None
    post.save(update_fields=["is_pinned", "pinned_at", "pinned_by"])
    return post


def notify_followers_of_post(post: ForumPost):
    """Bao nguoi dang theo doi chuyen muc/the cua bai moi duoc dang cong khai (khong bao tac gia).
    Goi khi bai duoc dang ngay, hoac khi Giao vu Khoa duyet bai dang cho kiem duyet."""
    notify_followers(
        [post.category, *post.tags.all()],
        f"Bài viết mới trong mục bạn theo dõi: {post.title}",
        post,
        exclude_user_ids=[post.author_id],
    )


def set_accepted_answer(post: ForumPost, comment, actor):
    """Chon (hoac bo chon neu bam lai) binh luan lam cau tra loi duoc chon cua bai hoi dap.
    Chi bao tac gia binh luan khi duoc chon moi (khong bao khi bo chon / tu chon cua chinh minh)."""
    if post.accepted_answer_id == comment.pk:
        post.accepted_answer = None
        post.save(update_fields=["accepted_answer"])
        return False
    post.accepted_answer = comment
    post.save(update_fields=["accepted_answer"])
    if comment.author_id != actor.pk:
        notify(
            recipient=comment.author, verb=Notification.Verb.ANSWER_ACCEPTED, actor=actor,
            message=f"Bình luận của bạn được chọn là câu trả lời cho “{post.title}”.", content_object=post,
        )
    return True


def create_post(author, category, title, body, tags=None, featured_image=None, is_question=False):
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    status = ContentStatus.PENDING_REVIEW if keyword else ContentStatus.PUBLISHED
    post = ForumPost.objects.create(
        author=author, category=category, title=title, body=body, status=status, featured_image=featured_image,
        is_question=is_question,
    )
    if tags:
        post.tags.set(tags)
    if keyword:
        log_action(
            actor=None,
            action="warn",
            reason=f"Tự động chuyển chờ kiểm duyệt do chứa từ khóa nhạy cảm: '{keyword.keyword}'",
            content_object=post,
        )
    else:
        notify_followers_of_post(post)
    return post, keyword


def update_post(post: ForumPost, editor, title, body, tags=None, featured_image=None, is_question=None):
    """Luu snapshot phien ban cu truoc khi ghi de + quet lai tu khoa nhay cam."""
    ForumPostEditHistory.objects.create(post=post, editor=editor, title=post.title, body=post.body)

    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    post.title = title
    post.body = body
    if featured_image is False:
        post.featured_image = None
    elif featured_image is not None:
        post.featured_image = featured_image
    post.edit_count += 1
    if is_question is not None:
        post.is_question = is_question
        if not is_question:
            post.accepted_answer = None  # khong con la cau hoi -> bo cau tra loi da chon
    if keyword:
        post.status = ContentStatus.PENDING_REVIEW
    post.save()
    if tags is not None:
        post.tags.set(tags)
    if keyword:
        log_action(
            actor=None,
            action="warn",
            reason=f"Tự động chuyển chờ kiểm duyệt do chứa từ khóa nhạy cảm: '{keyword.keyword}'",
            content_object=post,
        )
    return post, keyword
