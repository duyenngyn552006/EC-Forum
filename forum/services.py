from django.utils import timezone

from config.mixins import ContentStatus, PinLimitExceeded
from config.sanitize import sanitize_html
from moderation.services import find_sensitive_keyword, log_action

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


def create_post(author, category, title, body, tags=None, featured_image=None):
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    status = ContentStatus.PENDING_REVIEW if keyword else ContentStatus.PUBLISHED
    post = ForumPost.objects.create(
        author=author, category=category, title=title, body=body, status=status, featured_image=featured_image
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
    return post, keyword


def update_post(post: ForumPost, editor, title, body, tags=None, featured_image=None):
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
