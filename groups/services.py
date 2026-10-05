from django.utils import timezone

from accounts.models import User
from config.mixins import ContentStatus
from config.sanitize import sanitize_html
from moderation.services import find_sensitive_keyword, log_action
from moderation.models import ModerationLog
from notifications.models import Notification
from notifications.services import notify

from .models import Group, GroupMembership, GroupPost, GroupPostEditHistory


def request_create_group(creator, name, description, logo=None, cover_image=None):
    """Sinh vien -> pending, cho duyet. Giang vien/BCN/BCH -> active ngay, la leader luon."""
    if creator.role == User.Role.STUDENT:
        group = Group.objects.create(
            name=name, description=description, created_by=creator, status=Group.Status.PENDING,
            logo=logo, cover_image=cover_image,
        )
    else:
        group = Group.objects.create(
            name=name, description=description, created_by=creator,
            status=Group.Status.ACTIVE, approved_at=timezone.now(),
            logo=logo, cover_image=cover_image,
        )
        GroupMembership.objects.create(group=group, user=creator, role=GroupMembership.Role.LEADER)
    return group


def approve_group(group: Group, staff):
    group.status = Group.Status.ACTIVE
    group.approved_by = staff
    group.approved_at = timezone.now()
    group.reject_reason = ""
    group.save()
    GroupMembership.objects.get_or_create(
        group=group, user=group.created_by, defaults={"role": GroupMembership.Role.LEADER}
    )
    log_action(actor=staff, action=ModerationLog.Action.APPROVE_GROUP, reason="Duyệt yêu cầu tạo nhóm", target_user=group.created_by, content_object=group)
    notify(
        recipient=group.created_by, verb=Notification.Verb.GROUP_APPROVED, actor=staff,
        message=f"Nhóm '{group.name}' đã được duyệt.", content_object=group,
    )
    return group


def reject_group(group: Group, staff, reason: str):
    if not reason.strip():
        raise ValueError("Phải nhập lý do khi từ chối yêu cầu tạo nhóm.")
    group.status = Group.Status.REJECTED
    group.approved_by = staff
    group.approved_at = timezone.now()
    group.reject_reason = reason
    group.save()
    log_action(actor=staff, action=ModerationLog.Action.REJECT_GROUP, reason=reason, target_user=group.created_by, content_object=group)
    notify(
        recipient=group.created_by, verb=Notification.Verb.GROUP_REJECTED, actor=staff,
        message=f"Nhóm '{group.name}' bị từ chối: {reason}", content_object=group,
    )
    return group


def create_group_post(group, author, title, body, featured_image=None):
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    status = ContentStatus.PENDING_REVIEW if keyword else ContentStatus.PUBLISHED
    post = GroupPost.objects.create(
        group=group, author=author, title=title, body=body, status=status, featured_image=featured_image
    )
    if keyword:
        log_action(actor=None, action="warn", reason=f"Tự động chuyển chờ kiểm duyệt do từ khóa: '{keyword.keyword}'", content_object=post)
    return post, keyword


def update_group_post(post: GroupPost, editor, title, body, featured_image=None):
    GroupPostEditHistory.objects.create(post=post, editor=editor, title=post.title, body=post.body)
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
    if keyword:
        log_action(actor=None, action="warn", reason=f"Tự động chuyển chờ kiểm duyệt do từ khóa: '{keyword.keyword}'", content_object=post)
    return post, keyword
