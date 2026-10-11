"""Tag (@mention) thanh vien nhom - dung chung cho bai dang nhom (CKEditor Mention feature)
va binh luan (custom JS autocomplete tren textarea, xem interactions/static)."""
import re

MENTION_ID_ATTR_PATTERN = re.compile(r'data-mention="@user-(\d+)"')


def build_mention_feed(group):
    """Danh sach thanh vien nhom o dang CKEditor Mention feed (JSON-serializable) -
    dung cho ca CKEditor (config.mention.feeds[].feed) lan JS mention cua binh luan."""
    feed = []
    for membership in group.memberships.select_related("user").all():
        user = membership.user
        full_name = user.get_full_name() or user.email
        feed.append({"id": f"@user-{user.pk}", "text": f"@{full_name}"})
    return feed


def extract_mentioned_user_ids(html_body):
    """Tim id nguoi dung duoc @mention trong noi dung HTML da luu (CKEditor Mention)."""
    return [int(m) for m in MENTION_ID_ATTR_PATTERN.findall(html_body or "")]


def notify_mentions(actor, recipient_ids, content_object):
    from accounts.models import User
    from notifications.models import Notification
    from notifications.services import notify

    for user in User.objects.filter(pk__in=set(recipient_ids), is_active=True).exclude(pk=actor.pk):
        notify(
            recipient=user, verb=Notification.Verb.MENTION, actor=actor,
            message=f"{actor} đã gắn thẻ bạn trong một bài viết/bình luận.", content_object=content_object,
        )
