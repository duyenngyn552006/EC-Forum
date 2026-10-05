"""Logic nghiep vu kiem duyet dung chung: loc tu khoa nhay cam + ghi nhat ky.

Cac app forum/announcements/groups/interactions goi ham o day khi tao/sua
noi dung de bao dam luon di qua buoc tien kiem duyet, khong duplicate logic.
"""
from django.contrib.contenttypes.models import ContentType

from .models import ModerationLog, SensitiveKeyword


def find_sensitive_keyword(*texts):
    """Quet cac doan text qua danh sach tu khoa cam dang bat.

    Tra ve SensitiveKeyword dau tien khop duoc, hoac None neu sach.
    """
    active_keywords = list(SensitiveKeyword.objects.filter(is_active=True))
    if not active_keywords:
        return None
    combined = " ".join(t or "" for t in texts).lower()
    for kw in active_keywords:
        if kw.keyword.lower() in combined:
            return kw
    return None


def log_action(actor, action, reason, target_user=None, content_object=None):
    content_type = None
    object_id = None
    if content_object is not None:
        content_type = ContentType.objects.get_for_model(content_object)
        object_id = content_object.pk
    return ModerationLog.objects.create(
        actor=actor,
        target_user=target_user,
        content_type=content_type,
        object_id=object_id,
        action=action,
        reason=reason,
    )
