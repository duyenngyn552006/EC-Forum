from django.conf import settings
from django.utils import timezone

from config.mixins import ContentStatus, PinLimitExceeded
from config.sanitize import sanitize_html
from moderation.services import find_sensitive_keyword, log_action
from notifications.models import Notification
from notifications.tasks import broadcast_notification

from .models import Announcement, AnnouncementEditHistory


def pin_announcement(announcement: Announcement, actor):
    """Ghim trong pham vi cung `kind` (chinh thuc / su kien) - khong tu unpin bai cu."""
    if announcement.is_pinned:
        return announcement
    max_pinned = settings.MAX_PINNED_PER_CATEGORY
    current_pinned = Announcement.objects.filter(kind=announcement.kind, is_pinned=True).count()
    if current_pinned >= max_pinned:
        raise PinLimitExceeded(max_pinned)
    announcement.is_pinned = True
    announcement.pinned_at = timezone.now()
    announcement.pinned_by = actor
    announcement.save(update_fields=["is_pinned", "pinned_at", "pinned_by"])
    return announcement


def unpin_announcement(announcement: Announcement, actor):
    announcement.is_pinned = False
    announcement.pinned_at = None
    announcement.pinned_by = None
    announcement.save(update_fields=["is_pinned", "pinned_at", "pinned_by"])
    return announcement


def create_announcement(author, kind, title, body, event_datetime=None, featured_image=None):
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    status = ContentStatus.PENDING_REVIEW if keyword else ContentStatus.PUBLISHED
    announcement = Announcement.objects.create(
        author=author, kind=kind, title=title, body=body, status=status, event_datetime=event_datetime,
        featured_image=featured_image,
    )
    if keyword:
        log_action(
            actor=None, action="warn",
            reason=f"Tự động chuyển chờ kiểm duyệt do chứa từ khóa nhạy cảm: '{keyword.keyword}'",
            content_object=announcement,
        )
    elif status == ContentStatus.PUBLISHED:
        from accounts.models import User

        recipient_ids = list(User.objects.filter(is_active=True).values_list("id", flat=True))
        broadcast_notification.delay(
            recipient_ids=recipient_ids, verb=Notification.Verb.NEW_ANNOUNCEMENT,
            message=f"Thông báo mới: {title}", actor_id=author.id,
        )
    return announcement, keyword


def update_announcement(announcement: Announcement, editor, title, body, event_datetime=None, featured_image=None):
    AnnouncementEditHistory.objects.create(
        announcement=announcement, editor=editor, title=announcement.title, body=announcement.body
    )
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    announcement.title = title
    announcement.body = body
    announcement.event_datetime = event_datetime
    if featured_image is False:
        announcement.featured_image = None
    elif featured_image is not None:
        announcement.featured_image = featured_image
    announcement.edit_count += 1
    if keyword:
        announcement.status = ContentStatus.PENDING_REVIEW
    announcement.save()
    if keyword:
        log_action(
            actor=None, action="warn",
            reason=f"Tự động chuyển chờ kiểm duyệt do chứa từ khóa nhạy cảm: '{keyword.keyword}'",
            content_object=announcement,
        )
    return announcement, keyword
